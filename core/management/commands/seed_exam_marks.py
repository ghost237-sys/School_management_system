import random
from datetime import date
from typing import List

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import (
    AcademicYear,
    Term,
    Exam,
    Subject,
    SubjectGradingScheme,
    Grade,
    Student,
    Class,
)


class Command(BaseCommand):
    help = (
        "Seed exam marks (Grade rows) for every student in every class, for all base subjects.\n"
        "- Creates/uses the specified AcademicYear, Term and Exam.\n"
        "- Uses class.subjects if set; otherwise uses all base (non-component) subjects.\n"
        "- Scores are random within the provided range; grade letters use SubjectGradingScheme when available."
    )

    def add_arguments(self, parser):
        parser.add_argument("--year", type=str, required=True, help="Academic year label, e.g. 2025")
        parser.add_argument("--term", type=str, required=True, help="Term name, e.g. 'Term 1'")
        parser.add_argument("--exam", type=str, required=True, help="Exam name, e.g. 'Midterm T1 2025'")
        parser.add_argument(
            "--type", type=str, default="others",
            choices=["opener", "midterm", "endterm", "others"],
            help="Exam type (default: others)"
        )
        parser.add_argument("--score-min", type=int, default=40, help="Minimum random score (default: 40)")
        parser.add_argument("--score-max", type=int, default=95, help="Maximum random score (default: 95)")
        parser.add_argument("--update", action="store_true", help="If provided, update existing Grade scores instead of skipping")
        parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")

    def _get_or_create_year_term_exam(self, year_label: str, term_name: str, exam_name: str, exam_type: str) -> Exam:
        year_obj, _ = AcademicYear.objects.get_or_create(year=year_label)
        # Provide default dates if missing
        start = date(int(year_label), 1, 15)
        end = date(int(year_label), 3, 31)
        term_obj, _ = Term.objects.get_or_create(
            name=term_name,
            academic_year=year_obj,
            defaults={"start_date": start, "end_date": end},
        )
        # Create exam if missing
        today = timezone.now().date()
        exam_obj, _ = Exam.objects.get_or_create(
            name=exam_name,
            defaults={
                "term": term_obj,
                "level": None,
                "start_date": today,
                "end_date": today,
                "type": exam_type,
            },
        )
        # Ensure the exam is linked to the right term if it existed with different term
        if exam_obj.term_id != term_obj.id:
            exam_obj.term = term_obj
            exam_obj.save(update_fields=["term"])
        return exam_obj

    @transaction.atomic
    def handle(self, *args, **options):
        year_label: str = options["year"]
        term_name: str = options["term"]
        exam_name: str = options["exam"]
        exam_type: str = options["type"]
        score_min: int = options["score_min"]
        score_max: int = options["score_max"]
        do_update: bool = options["update"]
        seed = options["seed"]

        if seed is not None:
            random.seed(seed)

        if score_min < 0 or score_max > 100 or score_min > score_max:
            self.stderr.write("Invalid score range. Must satisfy 0 <= min <= max <= 100.")
            return

        exam = self._get_or_create_year_term_exam(year_label, term_name, exam_name, exam_type)

        base_subjects: List[Subject] = list(Subject.objects.filter(part_of__isnull=True).distinct())
        classes: List[Class] = list(Class.objects.prefetch_related("subjects", "students"))

        if not base_subjects:
            self.stdout.write(self.style.WARNING("No subjects found."))
            return
        if not classes:
            self.stdout.write(self.style.WARNING("No classes found."))
            return

        total_created = 0
        total_updated = 0

        # Build a cache for grading schemes
        grading_map = {gs.subject_id: gs for gs in SubjectGradingScheme.objects.select_related("subject")}

        # We will accumulate Grade objects for bulk_create
        to_create: List[Grade] = []

        for c in classes:
            # Use class.subjects if available; else use all base subjects
            c_subjects = list(c.subjects.all()) or base_subjects
            # Filter out any component subjects defensively (in case class.subjects contains them)
            c_subjects = [s for s in c_subjects if not s.part_of.exists()]

            students: List[Student] = list(c.students.select_related("user"))
            if not students:
                continue

            for s in c_subjects:
                scheme = grading_map.get(s.id)
                for st in students:
                    # Prepare a random score
                    score = random.randint(score_min, score_max)
                    grade_letter = None
                    if scheme:
                        grade_letter = scheme.get_grade_letter(score)

                    if do_update:
                        # Update-or-create behavior: try to update existing
                        updated = Grade.objects.filter(student=st, exam=exam, subject=s).update(
                            score=score, grade_letter=grade_letter
                        )
                        if updated:
                            total_updated += 1
                            continue

                    # Otherwise, plan to create if not exists
                    exists = Grade.objects.filter(student=st, exam=exam, subject=s).exists()
                    if exists:
                        continue

                    to_create.append(Grade(student=st, exam=exam, subject=s, score=score, grade_letter=grade_letter))

                    # Periodically flush to DB to avoid huge memory
                    if len(to_create) >= 2000:
                        Grade.objects.bulk_create(to_create, batch_size=1000)
                        total_created += len(to_create)
                        to_create.clear()

        if to_create:
            Grade.objects.bulk_create(to_create, batch_size=1000)
            total_created += len(to_create)

        self.stdout.write(self.style.SUCCESS(
            f"Exam '{exam.name}' ready. Created {total_created} grade rows; Updated {total_updated}."
        ))
