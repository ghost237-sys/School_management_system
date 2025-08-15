from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Teacher, Student, FeePayment, MpesaTransaction
from core.messaging_utils import _normalize_msisdn


class Command(BaseCommand):
    help = "Normalize phone numbers to E.164 format across Teacher, Student, FeePayment, and MpesaTransaction. Dry-run by default. Use --apply to persist."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply changes to the database. Without this flag, it only prints what would change.",
        )

    def handle(self, *args, **options):
        apply = options.get("apply", False)

        results = {
            "Teacher.phone": {"checked": 0, "changed": 0},
            "Student.phone": {"checked": 0, "changed": 0},
            "FeePayment.phone_number": {"checked": 0, "changed": 0},
            "MpesaTransaction.phone_number": {"checked": 0, "changed": 0},
        }

        def process_qs(qs, field_name, label):
            for obj in qs.iterator():
                results[label]["checked"] += 1
                original = getattr(obj, field_name)
                if not original:
                    continue
                normalized = _normalize_msisdn(original)
                if normalized != original:
                    results[label]["changed"] += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"{label} id={obj.pk}: '{original}' -> '{normalized}'"
                        )
                    )
                    if apply:
                        setattr(obj, field_name, normalized)
                        obj.save(update_fields=[field_name])

        # Run in a transaction if applying, so we can rollback on error
        ctx = transaction.atomic() if apply else nullcontext()
        with ctx:
            process_qs(Teacher.objects.all(), "phone", "Teacher.phone")
            process_qs(Student.objects.all(), "phone", "Student.phone")
            process_qs(FeePayment.objects.all(), "phone_number", "FeePayment.phone_number")
            process_qs(MpesaTransaction.objects.all(), "phone_number", "MpesaTransaction.phone_number")

        # Summary
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Normalization summary:"))
        for label, stats in results.items():
            self.stdout.write(
                f"- {label}: checked={stats['checked']}, to_change={stats['changed']}" +
                (" (APPLIED)" if apply else " (DRY-RUN)")
            )


# Python 3.7+ contextmanager for no-op when not applying
from contextlib import contextmanager

@contextmanager
def nullcontext():
    yield
