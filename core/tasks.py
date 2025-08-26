from celery import shared_task
from django.core.mail import get_connection, EmailMessage
from django.conf import settings

from .messaging_utils import send_sms_batch, _normalize_msisdn, _is_valid_ke_msisdn
from .models import NotificationJob, Grade, Exam, Student, FeeAssignment, FeePayment
from django.db.models import Sum
from django.utils import timezone
from collections import defaultdict


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=5, rate_limit='10/s')
def send_sms_bulk_task(self, phone_numbers, message):
    """Background task: send SMS to many recipients efficiently with retry.
    phone_numbers: list[str]
    message: str
    Returns (success_count, errors)
    """
    # We internally chunk in messaging_utils.send_sms_batch by provider request.
    # Here we call it directly for the full set to keep a single return value.
    success, errors = send_sms_batch(phone_numbers, message)
    return success, errors


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3, rate_limit='5/s')
def send_email_bcc_task(self, subject, message, recipient_chunk):
    """Background task: send a single BCC email to up to N recipients using one SMTP connection."""
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    with get_connection() as connection:
        email = EmailMessage(
            subject=subject,
            body=message,
            from_email=from_email,
            to=[],
            bcc=recipient_chunk,
            connection=connection,
        )
        connection.send_messages([email])
    return len(recipient_chunk)


@shared_task(bind=True)
def send_exam_publish_notifications(self, job_id, exam_id, base_url):
    """Background: send notifications for published exam and update NotificationJob."""
    job = NotificationJob.objects.get(pk=job_id)
    try:
        exam = Exam.objects.get(pk=exam_id)
        grades_qs = (
            Grade.objects
            .filter(exam=exam)
            .select_related('student__user', 'student__class_group', 'subject')
        )
        # Build map per student
        student_grades = defaultdict(list)
        for g in grades_qs.iterator():
            student_grades[g.student_id].append(g)
        total = len(student_grades)
        job.mark_running(total=total)

        # Minimal imports here to avoid circulars
        from django.core.mail import send_mail
        from django.urls import reverse
        from django.core import signing
        from landing.models import SiteSettings

        school_name = None
        ss = SiteSettings.objects.first()
        if ss and ss.school_name:
            school_name = ss.school_name
        if not school_name:
            school_name = getattr(settings, 'SCHOOL_NAME', 'Your School')

        # Precompute ranks
        totals = {}
        class_groups = defaultdict(list)
        levels = defaultdict(list)
        for sid, glist in student_grades.items():
            total_score = sum((g.score or 0) for g in glist)
            totals[sid] = total_score
            s = glist[0].student
            cid = getattr(s.class_group, 'id', None)
            lvl = getattr(s.class_group, 'level', None)
            if cid is not None:
                class_groups[cid].append((sid, total_score))
            if lvl is not None:
                levels[lvl].append((sid, total_score))

        def build_ranks(pairs):
            pairs_sorted = sorted(pairs, key=lambda x: x[1], reverse=True)
            ranks = {}
            current_rank = 0
            last_total = None
            for idx, (sid, total_score) in enumerate(pairs_sorted, start=1):
                if last_total is None or total_score != last_total:
                    current_rank = idx
                    last_total = total_score
                ranks[sid] = (current_rank, len(pairs_sorted))
            return ranks

        class_ranks = {cid: build_ranks(pairs) for cid, pairs in class_groups.items()}
        level_ranks = {lvl: build_ranks(pairs) for lvl, pairs in levels.items()}

        # Batch send via SMS/email
        phone_recipients = []
        email_messages = []
        from django.core.mail import EmailMessage as DMEmail
        for sid, glist in student_grades.items():
            try:
                student = glist[0].student
                user = getattr(student, 'user', None)
                email = getattr(user, 'email', None) if user else None
                phone = getattr(student, 'phone', None)
                glist_sorted = sorted(glist, key=lambda g: g.subject.name)
                parts = []
                for g in glist_sorted:
                    letter = g.grade_letter or ''
                    parts.append(f"{g.subject.name.split()[0][:6]}:{letter or int(g.score)}")
                subj_sms = ", ".join(parts[:6])
                if len(parts) > 6:
                    subj_sms += f" +{len(parts)-6}"
                cid = getattr(student.class_group, 'id', None)
                lvl = getattr(student.class_group, 'level', None)
                c_rank = class_ranks.get(cid, {}).get(sid)
                l_rank = level_ranks.get(lvl, {}).get(sid)
                c_rank_str = f"{c_rank[0]}/{c_rank[1]}" if c_rank else "-"
                l_rank_str = f"{l_rank[0]}/{l_rank[1]}" if l_rank else "-"
                try:
                    profile_url = f"{base_url}".rstrip('/') + reverse('student_profile', args=[student.id]) + f"?exam={exam.id}"
                except Exception:
                    profile_url = f"{base_url}"
                sms_text = (
                    f"{school_name}: Results {exam.term.name} - {exam.name}. "
                    f"{subj_sms}. Pos(Class): {c_rank_str}, Pos(Level): {l_rank_str}. "
                    f"View: {profile_url}"
                )
                if phone:
                    phone_recipients.append(phone)

                if email:
                    full_list = ", ".join(f"{g.subject.name}:{g.grade_letter or g.score}" for g in glist_sorted)
                    payload = {'sid': student.id, 'eid': exam.id}
                    token = signing.dumps(payload, salt='resultslip', compress=True)
                    try:
                        pdf_url = f"{base_url}".rstrip('/') + reverse('download_result_slip_signed', args=[token])
                    except Exception:
                        pdf_url = profile_url
                    body = (
                        f"Dear {user.get_full_name() if user else 'Student'},\n\n"
                        f"Your results for {exam.term.name} - {exam.name} have been released.\n\n"
                        f"Subjects: {full_list}\n"
                        f"Class position: {c_rank_str}\n"
                        f"Level position: {l_rank_str}\n\n"
                        f"Download your PDF result slip: {pdf_url}\n"
                        f"Or view online: {profile_url}\n\n"
                        f"Regards,\n{school_name}"
                    )
                    email_messages.append((f"{school_name}: Results released - {exam.name}", body, email))

                # Increment processed per student
                job.incr(success=True)
            except Exception:
                job.incr(success=False)

        # Send SMS in batches via existing task for provider chunking
        if phone_recipients:
            send_sms_bulk_task.delay(phone_recipients, f"{school_name}: Results released. Check portal.")

        # Send emails in BCC chunks
        chunk = 100
        for i in range(0, len(email_messages), chunk):
            subject = None
            body = None
            recipients = []
            for s, b, e in email_messages[i:i+chunk]:
                subject = s or subject
                body = b or body
                recipients.append(e)
            if recipients and subject and body:
                send_email_bcc_task.delay(subject, body, recipients)

        job.mark_done()
    except Exception as e:
        job.mark_failed(str(e))
        raise


@shared_task(bind=True)
def send_fee_arrears_notifications(self, job_id, current_term_id=None, class_group_id=None):
    job = NotificationJob.objects.get(pk=job_id)
    try:
        # Compute balances
        students = Student.objects.select_related('user', 'class_group')
        if class_group_id:
            students = students.filter(class_group_id=class_group_id)
        if current_term_id:
            terms = [current_term_id]
        else:
            terms = list(FeeAssignment.objects.values_list('term_id', flat=True).distinct())

        # Pre-aggregate payments by student up to term
        payments = FeePayment.objects.values('student_id').annotate(total_paid=Sum('amount_paid'))
        paid_map = {p['student_id']: p['total_paid'] or 0 for p in payments}

        # Pre-aggregate assignments per class
        assign_map = {}
        for fa in FeeAssignment.objects.filter(term_id__in=terms).values('class_group_id').annotate(total=Sum('amount')):
            assign_map[fa['class_group_id']] = fa['total'] or 0

        # Determine arrears list
        arrears = []
        for s in students.iterator():
            total_assigned = assign_map.get(getattr(s.class_group, 'id', None), 0)
            balance = float(total_assigned) - float(paid_map.get(s.id, 0))
            if balance > 0.01:
                arrears.append((s, balance))

        job.mark_running(total=len(arrears))

        # Prepare notifications
        emails = []
        phones = []
        for s, bal in arrears:
            try:
                user = s.user
                msg = (
                    f"Dear {user.get_full_name() or user.username},\n\n"
                    f"Our records indicate an outstanding fee balance of Ksh. {bal:.2f}.\n"
                    f"Please make arrangements to settle the outstanding amount.\n\n"
                    f"Thank you,\nSchool Accounts"
                )
                if user and user.email:
                    emails.append(("Fee Payment Arrears Notification", msg, user.email))
                if hasattr(user, 'phone') and user.phone:
                    phones.append(user.phone)
                job.incr(success=True)
            except Exception:
                job.incr(success=False)

        # Dispatch
        if phones:
            send_sms_bulk_task.delay(phones, "School: Fee arrears reminder. Check your email/portal.")
        chunk = 100
        for i in range(0, len(emails), chunk):
            subject = None
            body = None
            recipients = []
            for s, b, e in emails[i:i+chunk]:
                subject = s or subject
                body = b or body
                recipients.append(e)
            if recipients and subject and body:
                send_email_bcc_task.delay(subject, body, recipients)

        job.mark_done()
    except Exception as e:
        job.mark_failed(str(e))
        raise
