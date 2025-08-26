import random
import string
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import Student, Term, FeeAssignment, FeePayment


class Command(BaseCommand):
    help = (
        "Generate random FeePayment records for students in all classes. "
        "Payments are linked to existing FeeAssignment for each student's class and a chosen term."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--term-id",
            type=int,
            default=None,
            help="ID of the Term to use. If omitted, the latest Term (by start_date then id) is used.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Number of payments to create in a single database transaction (default: 1000)",
        )
        parser.add_argument(
            "--per-student",
            type=int,
            default=1,
            help="Number of random payments to create per student (default: 1)",
        )
        parser.add_argument(
            "--min",
            dest="min_amount",
            type=Decimal,
            default=Decimal("100.00"),
            help="Minimum random payment amount (default: 100.00)",
        )
        parser.add_argument(
            "--max",
            dest="max_amount",
            type=Decimal,
            default=Decimal("2000.00"),
            help="Maximum random payment amount (default: 2000.00)",
        )
        parser.add_argument(
            "--status",
            choices=["pending", "approved", "rejected"],
            default="approved",
            help="Payment verification status to set on generated records (default: approved)",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=None,
            help="Random seed for reproducibility (optional)",
        )
        parser.add_argument(
            "--sample-count",
            type=int,
            default=None,
            help="Randomly select exactly this many students to create payments for (overrides --sample-fraction).",
        )
        parser.add_argument(
            "--sample-fraction",
            type=float,
            default=None,
            help="Randomly select this fraction (0-1] of students to create payments for (ignored if --sample-count is provided).",
        )

    def handle(self, *args, **options):
        seed = options.get("seed")
        if seed is not None:
            random.seed(seed)

        batch_size = options["batch_size"]
        per_student = options["per_student"]
        min_amount: Decimal = options["min_amount"]
        max_amount: Decimal = options["max_amount"]
        status = options["status"]
        sample_count: int | None = options.get("sample_count")
        sample_fraction: float | None = options.get("sample_fraction")

        if min_amount < 0 or max_amount <= 0 or min_amount > max_amount:
            raise CommandError("Invalid amount range: ensure 0 <= --min <= --max and --max > 0")

        term = self._resolve_term(options.get("term_id"))
        if not term:
            raise CommandError(
                "No Term found. Create at least one Term or pass a valid --term-id."
            )

        self.stdout.write(self.style.NOTICE(f"Using term: {term} (id={term.id})"))

        # Preload assignments by (class_id)
        assignments = dict(FeeAssignment.objects
            .filter(term=term)
            .values_list('class_group_id', 'id')
        )
        if not assignments:
            self.stdout.write(self.style.WARNING(
                f"No FeeAssignment found for term {term}. No payments will be created."
            ))
            return

        # Get student IDs with valid class assignments
        student_ids = list(Student.objects
            .filter(class_group_id__in=assignments.keys(), graduated=False)
            .values_list('id', flat=True)
        )
        
        if not student_ids:
            self.stdout.write(self.style.WARNING("No eligible students found with class assignments."))
            return

        # Apply random sampling if requested
        if sample_count is not None:
            if sample_count < 0:
                raise CommandError("--sample-count must be >= 0")
            sample_size = min(sample_count, len(student_ids))
            selected_ids = random.sample(student_ids, sample_size)
        elif sample_fraction is not None:
            if not (0 < sample_fraction <= 1):
                raise CommandError("--sample-fraction must be in the range (0, 1]")
            sample_size = max(1, int(round(sample_fraction * len(student_ids))))
            selected_ids = random.sample(student_ids, sample_size)
        else:
            selected_ids = student_ids

        self.stdout.write(f"Creating payments for {len(selected_ids)} students...")
        
        # Process in batches to manage memory
        batch = []
        count_created = 0
        count_skipped = 0
        
        for i, student_id in enumerate(selected_ids, 1):
            if i % 100 == 0:
                self.stdout.write(f"Processed {i}/{len(selected_ids)} students...")
                
            # Get a fresh student with class info for each batch
            student = Student.objects.get(id=student_id)
            class_id = student.class_group_id
            
            if class_id not in assignments:
                count_skipped += 1
                continue
                
            for _ in range(per_student):
                amount = self._random_amount(min_amount, max_amount)
                method = random.choice(["cash", "bank"])
                reference = f"{'CASH' if method == 'cash' else 'BANK'}-{timezone.now().strftime('%Y%m%d%H%M%S%f')}-{random.randint(1000, 9999)}"
                
                batch.append(FeePayment(
                    student_id=student_id,
                    fee_assignment_id=assignments[class_id],
                    amount_paid=amount,
                    payment_method=method,
                    reference=reference,
                    status=status,
                ))
                
                # Process batch when it reaches batch_size
                if len(batch) >= batch_size:
                    FeePayment.objects.bulk_create(batch)
                    count_created += len(batch)
                    batch = []
        
        # Process any remaining items in the batch
        if batch:
            FeePayment.objects.bulk_create(batch)
            count_created += len(batch)
        
        self.stdout.write(self.style.SUCCESS(
            f"Created {count_created} FeePayment(s). "
            f"Skipped {count_skipped} student(s) with no FeeAssignment for term."
        ))

    def _resolve_term(self, term_id: int | None) -> Term | None:
        if term_id:
            try:
                return Term.objects.get(id=term_id)
            except Term.DoesNotExist:
                raise CommandError(f"Term with id={term_id} does not exist")
        # fallback: latest by start_date then id
        qs = Term.objects.all()
        if qs.filter(start_date__isnull=False).exists():
            return qs.order_by("-start_date", "-id").first()
        return qs.order_by("-id").first()

    def _random_amount(self, min_amount: Decimal, max_amount: Decimal) -> Decimal:
        # pick a random amount with two decimal places within range
        cents_min = int(min_amount * 100)
        cents_max = int(max_amount * 100)
        value_cents = random.randint(cents_min, cents_max)
        return Decimal(value_cents) / Decimal(100)
