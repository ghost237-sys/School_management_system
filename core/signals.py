from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.core.cache import cache
import logging

from .models import Student, FeePayment, DefaultTimetable, Teacher, User, FeeAssignment, MpesaTransaction
from .messaging_utils import send_sms, send_bulk_sms
from .messaging_utils import _normalize_msisdn

logger = logging.getLogger(__name__)

def _school_name():
    name = getattr(settings, 'SCHOOL_NAME', 'Your School')
    try:
        from landing.models import SiteSettings
        s = SiteSettings.objects.first()
        if s and s.school_name:
            name = s.school_name
    except Exception:
        pass


# --- Auto-normalize phone numbers before save ---
@receiver(pre_save, sender=Teacher)
def normalize_teacher_phone(sender, instance: Teacher, **kwargs):
    try:
        if instance.phone:
            instance.phone = _normalize_msisdn(instance.phone)
    except Exception:
        # don't block saves
        pass


@receiver(pre_save, sender=Student)
def normalize_student_phone(sender, instance: Student, **kwargs):
    try:
        if instance.phone:
            instance.phone = _normalize_msisdn(instance.phone)
    except Exception:
        pass


@receiver(pre_save, sender=FeePayment)
def normalize_fee_payment_phone(sender, instance: FeePayment, **kwargs):
    try:
        if instance.phone_number:
            instance.phone_number = _normalize_msisdn(instance.phone_number)
    except Exception:
        pass


@receiver(pre_save, sender=MpesaTransaction)
def normalize_mpesa_tx_phone(sender, instance: MpesaTransaction, **kwargs):
    try:
        if instance.phone_number:
            instance.phone_number = _normalize_msisdn(instance.phone_number)
    except Exception:
        pass


# 2) After admission/enrollment of a student
@receiver(post_save, sender=Student)
def notify_on_student_admission(sender, instance: Student, created, **kwargs):
    if not created:
        return
    school = _school_name()
    parts = []
    if instance.user:
        parts.append(instance.user.get_full_name() or instance.user.username)
    if instance.admission_no:
        parts.append(f"Adm: {instance.admission_no}")
    who = " ".join(parts) if parts else f"Student #{instance.pk}"
    msg = f"{school}: Admission successful for {who}. Welcome!"
    if instance.phone:
        send_sms(instance.phone, msg)


# 3) After payment of fees -> send to payer's number and student's number including transaction id
@receiver(post_save, sender=FeePayment)
def notify_on_fee_payment(sender, instance: FeePayment, created, **kwargs):
    if not created:
        return
    school = _school_name()
    student = instance.student
    who = None
    if student and student.user:
        who = student.user.get_full_name() or student.user.username
    tx = instance.reference or (instance.mpesa_transaction.mpesa_receipt if instance.mpesa_transaction and instance.mpesa_transaction.mpesa_receipt else None)
    tx_part = f" TxID: {tx}." if tx else ""
    msg = f"{school}: Fee payment of {instance.amount_paid} received for {who or 'student'}.{tx_part} Thank you."
    targets = []
    if instance.phone_number:
        targets.append(instance.phone_number)
    if student and student.phone:
        targets.append(student.phone)
    if targets:
        send_bulk_sms(targets, msg)


# 4) Notify teachers after timetable updates
@receiver(post_save, sender=DefaultTimetable)
def notify_teachers_on_timetable_update(sender, instance: DefaultTimetable, **kwargs):
    # Debounce with atomic cache.add so only the first save in a burst sends SMS
    # Cooldown window (seconds) – adjust as needed
    cooldown = int(getattr(settings, 'TIMETABLE_NOTIFY_COOLDOWN', 120))
    lock_key = "timetable_update_notice_lock"
    try:
        # cache.add returns True only if the key did not exist, atomically
        acquired = cache.add(lock_key, timezone.now().isoformat(), timeout=cooldown)
        if not acquired:
            logger.info("Timetable update notice suppressed within cooldown window (%ss)", cooldown)
            return
    except Exception:
        # If cache not configured, we still proceed, but only once per process execution
        logger.warning("Cache not configured; proceeding without debounce lock")

    school = _school_name()
    msg = f"{school}: Timetable has been updated. Please review your schedule in the portal."
    raw_phones = Teacher.objects.exclude(phone__isnull=True).exclude(phone__exact='').values_list('phone', flat=True)
    teacher_phones = sorted({p for p in raw_phones if p})  # unique phones only
    logger.info("Timetable update detected; unique recipients=%d", len(teacher_phones))
    if teacher_phones:
        ok_count, errors = send_bulk_sms(teacher_phones, msg)
        if errors:
            logger.error("Timetable SMS errors (%d): %s", len(errors), "; ".join(errors[:10]))
        logger.info("Timetable SMS sent: success=%d, total=%d", ok_count, len(teacher_phones))
    else:
        logger.warning("No teacher phone numbers found; timetable SMS skipped")

    # Also notify by email when available (console backend in dev)
    teacher_emails = list(
        Teacher.objects.select_related('user')
        .exclude(user__email__isnull=True)
        .exclude(user__email__exact='')
        .values_list('user__email', flat=True)
    )
    if teacher_emails:
        try:
            send_mail(
                subject=f"{school}: Timetable updated",
                message="Please review your updated schedule in the portal.",
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
                recipient_list=teacher_emails,
                fail_silently=True,
            )
            logger.info("Timetable email notices sent to %d teacher(s)", len(teacher_emails))
        except Exception as e:
            logger.error("Timetable email send failed: %s", e)
