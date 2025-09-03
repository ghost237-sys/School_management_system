from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail, get_connection
from django.core.cache import cache
import logging

from .models import Student, FeePayment, DefaultTimetable, Teacher, User, FeeAssignment, MpesaTransaction, TeacherResponsibility, Exam
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
    # Email counterpart if available
    try:
        if instance.user and getattr(instance.user, 'email', None):
            send_mail(
                subject=f"{school}: Admission successful",
                message=msg,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
                recipient_list=[instance.user.email],
                fail_silently=True,
            )
    except Exception:
        pass


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
    # Email counterpart to student if email available
    try:
        if student and student.user and getattr(student.user, 'email', None):
            send_mail(
                subject=f"{school}: Fee payment received",
                message=msg,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
                recipient_list=[student.user.email],
                fail_silently=True,
            )
    except Exception:
        pass

@receiver(post_save, sender=Exam)
def notify_on_results_published(sender, instance: Exam, created, **kwargs):
    """When exam results are published, notify relevant students via SMS and email.
    If published_at isn't set yet when results_published becomes True, set it.
    """
    try:
        if not instance.results_published:
            return
        # Ensure published_at is set once
        if not instance.published_at:
            instance.published_at = timezone.now()
            try:
                instance.save(update_fields=['published_at'])
            except Exception:
                pass

        school = _school_name()
        level = getattr(instance, 'level', None)
        qs = Student.objects.exclude(phone__isnull=True).exclude(phone__exact='')
        if level:
            qs = qs.filter(class_group__level=str(level))

        # SMS
        phones = list(qs.values_list('phone', flat=True))
        if phones:
            text = f"{school}: Results for '{instance.name}' have been published. Please check the portal."
            try:
                send_bulk_sms(phones, text)
            except Exception:
                pass

        # Email
        try:
            emails = list(
                qs.select_related('user')
                .exclude(user__email__isnull=True)
                .exclude(user__email__exact='')
                .values_list('user__email', flat=True)
            )
            if emails:
                subject = f"{school}: Exam results published — {instance.name}"
                body = f"Dear Student,\n\nResults for '{instance.name}' have been published. Please log in to the portal to view your results.\n\nRegards,\n{school}"
                with get_connection() as connection:
                    for addr in emails:
                        try:
                            send_mail(
                                subject=subject,
                                message=body,
                                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
                                recipient_list=[addr],
                                fail_silently=True,
                                connection=connection,
                            )
                        except Exception:
                            pass
        except Exception:
            pass
    except Exception:
        # Never block DB save due to notification issues
        logger.error("notify_on_results_published error")


# 3b) Notify a teacher when a responsibility is assigned
@receiver(post_save, sender=TeacherResponsibility)
def notify_on_responsibility_assigned(sender, instance: TeacherResponsibility, created, **kwargs):
    if not created:
        return
    try:
        school = _school_name()
        teacher = instance.teacher
        teacher_name = None
        teacher_email = None
        if teacher and teacher.user:
            teacher_name = teacher.user.get_full_name() or teacher.user.username
            teacher_email = getattr(teacher.user, 'email', None)

        # Compose message
        date_part = []
        if instance.start_date:
            date_part.append(f"from {instance.start_date}")
        if instance.end_date:
            date_part.append(f"to {instance.end_date}")
        date_str = (" " + " ".join(date_part)) if date_part else ""
        details = f" Details: {instance.details}" if instance.details else ""
        assigned_by = None
        if instance.assigned_by:
            assigned_by = instance.assigned_by.get_full_name() or instance.assigned_by.username
        by_str = f" Assigned by: {assigned_by}." if assigned_by else ""

        text = f"{school}: You have been assigned a responsibility — '{instance.responsibility}'{date_str}.{by_str}{details}"

        # SMS
        if getattr(teacher, 'phone', None):
            try:
                send_sms(teacher.phone, text)
            except Exception:
                logger.warning("Failed to send responsibility SMS to %s", teacher.phone)

        # Email
        if teacher_email:
            try:
                send_mail(
                    subject=f"{school}: New responsibility assigned",
                    message=text,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
                    recipient_list=[teacher_email],
                    fail_silently=True,
                )
            except Exception as e:
                logger.warning("Failed to send responsibility email to %s: %s", teacher_email, e)
    except Exception as e:
        # Never block DB save due to notification issues
        logger.error("notify_on_responsibility_assigned error: %s", e)

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

    # Also notify by email: per-recipient so each appears in Sent with its own To:
    try:
        teacher_emails = list(
            Teacher.objects.select_related('user')
            .exclude(user__email__isnull=True)
            .exclude(user__email__exact='')
            .values_list('user__email', flat=True)
        )
        if not teacher_emails:
            logger.warning("No teacher emails found; timetable email skipped")
        else:
            subject = f"{school}: Timetable updated"
            body = "Please review your updated schedule in the portal."
            sent = 0
            errors = 0
            # Reuse a single SMTP connection for efficiency
            with get_connection() as connection:
                for addr in teacher_emails:
                    try:
                        send_mail(
                            subject=subject,
                            message=body,
                            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
                            recipient_list=[addr],
                            fail_silently=True,
                            connection=connection,
                        )
                        sent += 1
                    except Exception:
                        errors += 1
            logger.info("Timetable emails sent per-recipient: success=%d, total=%d, errors=%d", sent, len(teacher_emails), errors)
    except Exception as e:
        logger.error("Timetable email send (per-recipient) failed: %s", e)


# --- Limit admin to 2 concurrent devices/sessions ---
from django.contrib.auth.signals import user_logged_in
from django.contrib.sessions.models import Session


@receiver(user_logged_in)
def limit_role_concurrent_sessions(sender, user, request, **kwargs):
    """
    Keep at most 2 active sessions for admin users.
    Strategy: on every successful login, set a login timestamp in the current session,
    then enumerate all sessions and prune the oldest ones for this user beyond the limit.
    """
    try:
        # Enforce per-role session limits
        if not isinstance(user, User):
            return
        role = getattr(user, 'role', None) or 'user'
        limits = getattr(settings, 'ROLE_SESSION_LIMITS', {})
        limit = int(limits.get(role, limits.get('default', 2)))
        # Ensure at least 1
        if limit < 1:
            limit = 1

        # Mark current session with a login timestamp for ordering
        try:
            if request and hasattr(request, 'session'):
                request.session['login_ts'] = timezone.now().isoformat()
                # Capture device metadata for sessions page
                try:
                    ua = (request.META.get('HTTP_USER_AGENT') or '')[:300]
                    ip = (
                        (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
                        or request.META.get('REMOTE_ADDR')
                        or ''
                    )
                    request.session['device_user_agent'] = ua
                    request.session['device_ip'] = ip
                    request.session['device_login_time'] = timezone.now().isoformat()
                except Exception:
                    # Non-fatal; don't block login if headers are missing
                    pass
                request.session.modified = True
        except Exception:
            pass

        # Gather all sessions that belong to this user
        sessions = []
        for s in Session.objects.filter(expire_date__gt=timezone.now()):
            try:
                data = s.get_decoded()
                uid = data.get('_auth_user_id')
                if uid and str(uid) == str(user.pk):
                    login_ts = data.get('login_ts')
                    sessions.append((s, login_ts))
            except Exception:
                # Skip corrupt/undecodable sessions
                continue

        # If within limit, nothing to do
        if len(sessions) <= limit:
            return

        # Sort by login_ts (newest first); fall back to expire_date then session_key
        def sort_key(item):
            s, ts = item
            # parse ts to datetime if possible
            dt = None
            if ts:
                try:
                    dt = timezone.datetime.fromisoformat(ts)
                    if timezone.is_naive(dt):
                        dt = timezone.make_aware(dt, timezone.get_current_timezone())
                except Exception:
                    dt = None
            return (
                0 if dt else 1,  # prefer those with timestamp
                -(dt.timestamp()) if dt else 0,
                s.expire_date or timezone.now(),
                s.session_key,
            )

        sessions.sort(key=sort_key)

        # Keep top 'limit' sessions, delete the rest
        to_delete = sessions[limit:]
        for s, _ in to_delete:
            try:
                s.delete()
            except Exception:
                continue
    except Exception as e:
        # Never break login flow due to pruning issues
        logger.error("Admin session limit enforcement failed: %s", e)
