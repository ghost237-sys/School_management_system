from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Sum
from django.conf import settings

from core.models import Student, FeeAssignment, FeePayment, Term, Teacher
from core.messaging_utils import send_sms, send_bulk_sms


def school_name():
    name = getattr(settings, 'SCHOOL_NAME', 'Your School')
    try:
        from landing.models import SiteSettings
        s = SiteSettings.objects.first()
        if s and s.school_name:
            name = s.school_name
    except Exception:
        pass
    return name


def calc_balance(student):
    total_billed = FeeAssignment.objects.filter(class_group=student.class_group).aggregate(total=Sum('amount'))['total'] or 0
    total_paid = FeePayment.objects.filter(student=student).aggregate(total=Sum('amount_paid'))['total'] or 0
    return total_billed - total_paid


class Command(BaseCommand):
    help = "Send scheduled SMS notifications: bi-weekly balances and term date reminders. Run daily."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Print actions without sending SMS')

    def handle(self, *args, **opts):
        dry = opts.get('dry_run', False)
        today = timezone.localdate()
        now = timezone.now()
        school = school_name()

        # 1) Bi-weekly to all parents/students with fee balances
        # Send on alternating weeks: e.g., every 14 days from a fixed anchor (Jan 1st of current year)
        anchor = timezone.datetime(year=today.year, month=1, day=1).date()
        days_since_anchor = (today - anchor).days
        if days_since_anchor % 14 == 0:
            targets = []
            for st in Student.objects.exclude(phone__isnull=True).exclude(phone__exact=''):
                bal = calc_balance(st)
                if bal > 0:
                    msg = f"{school}: Fee balance for {st.full_name if hasattr(st, 'full_name') else (st.user.get_full_name() if st.user else 'student')} is KES {bal:,.2f}. Please clear at your earliest convenience."
                    if dry:
                        self.stdout.write(f"[DRY] {st.phone} <- {msg}")
                    else:
                        send_sms(st.phone, msg)

        # 5/6/7/8/9) Term-date reminders around closing and opening
        current_term = Term.objects.filter(start_date__lte=today, end_date__gte=today).order_by('-start_date').first()
        upcoming_term = Term.objects.filter(start_date__gte=today).order_by('start_date').first()

        def notify_all_students(text):
            phones = list(Student.objects.exclude(phone__isnull=True).exclude(phone__exact='').values_list('phone', flat=True))
            if not phones:
                return
            msg = f"{school}: {text}"
            if dry:
                for p in phones:
                    self.stdout.write(f"[DRY] {p} <- {msg}")
            else:
                send_bulk_sms(phones, msg)

        # Closing reminders relative to current_term.end_date
        if current_term and current_term.end_date:
            days_to_close = (current_term.end_date - today).days
            if days_to_close == 5:
                notify_all_students("5 days before end of term. Kindly prepare and clear any balances.")
            if days_to_close == 2:
                notify_all_students("2 days before closing date. Kindly ensure fees and clearances are completed.")
            if days_to_close == 0:
                notify_all_students("Today is closing day. We wish you a restful break.")

        # Opening reminders relative to upcoming_term.start_date
        if upcoming_term and upcoming_term.start_date:
            days_to_open = (upcoming_term.start_date - today).days
            if days_to_open == 5:
                notify_all_students("5 days before opening day. Welcome back preparations underway.")
            if days_to_open == 0:
                notify_all_students("School opens today. Welcome back!")

        # Teachers timetable update reminders are sent via a signal when the timetable is saved; nothing here.

        self.stdout.write(self.style.SUCCESS("schedule_notifications completed"))
