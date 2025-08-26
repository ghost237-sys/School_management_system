import random
from collections import defaultdict
from typing import List, Tuple

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Class, Subject, Teacher, TeacherClassAssignment


class Command(BaseCommand):
    help = (
        "Assign subject teachers to every class. Optionally refresh Class.subjects and reset existing assignments.\n"
        "- If --refresh-class-subjects is provided, each class gets a fresh random set of subjects.\n"
        "- If --reset is provided, existing TeacherClassAssignment rows are cleared before assigning.\n"
        "- The assignment prefers teachers who have the subject in Teacher.subjects.\n"
        "- Tries to ensure each teacher gets at least one assignment where slots >= teachers."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Delete existing TeacherClassAssignment records before assigning."
        )
        parser.add_argument(
            "--refresh-class-subjects", action="store_true",
            help="Refresh Class.subjects with a random subset before assigning."
        )
        parser.add_argument(
            "--subjects-per-class", type=int, default=6,
            help="Number of subjects to assign per class when refreshing (default: 6)."
        )
        parser.add_argument(
            "--seed", type=int, default=None,
            help="Random seed for reproducibility."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        do_reset = options["reset"]
        do_refresh = options["refresh_class_subjects"]
        subjects_per_class = options["subjects_per_class"]
        seed = options["seed"]

        if seed is not None:
            random.seed(seed)

        classes: List[Class] = list(Class.objects.prefetch_related("subjects"))
        # Base subjects = subjects that are NOT components (i.e., not child in SubjectComponent)
        subjects_qs = Subject.objects.filter(part_of__isnull=True).distinct()
        subjects: List[Subject] = list(subjects_qs)
        teachers: List[Teacher] = list(Teacher.objects.prefetch_related("subjects", "user"))

        if not classes:
            self.stdout.write(self.style.WARNING("No classes found."))
            return
        if not subjects:
            self.stdout.write(self.style.WARNING("No subjects found."))
            return
        if not teachers:
            self.stdout.write(self.style.WARNING("No teachers found."))
            return

        if do_reset:
            deleted, _ = TeacherClassAssignment.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} existing TeacherClassAssignment rows."))

        # Optionally refresh Class.subjects: set ALL base subjects for every class
        if do_refresh:
            for c in classes:
                c.subjects.set(subjects)
            self.stdout.write(self.style.SUCCESS("Refreshed Class.subjects to include all base subjects for all classes."))

        # Build slots: (class, subject) for ALL base subjects in EVERY class
        slots: List[Tuple[Class, Subject]] = []
        for c in classes:
            for s in subjects:
                slots.append((c, s))

        if not slots:
            self.stdout.write(self.style.WARNING("No (class, subject) slots to assign."))
            return

        # Eligible teachers per subject
        eligible_by_subject = defaultdict(list)  # subject_id -> List[Teacher]
        for t in teachers:
            for s in t.subjects.all():
                eligible_by_subject[s.id].append(t)
        for sub_id in eligible_by_subject:
            random.shuffle(eligible_by_subject[sub_id])

        # Teacher load tracking to balance
        load = {t.id: 0 for t in teachers}
        teacher_by_id = {t.id: t for t in teachers}

        # Sort slots by scarcity: subjects with fewer eligible teachers first
        def scarcity_key(slot):
            _, subj = slot
            elig = eligible_by_subject.get(subj.id, [])
            return (len(elig), subj.id)

        slots.sort(key=scarcity_key)

        assignments: List[TeacherClassAssignment] = []
        seen = set()  # avoid duplicates (teacher_id, class_id, subject_id)

        # Round-robin assignment ensuring fairness and subject matching
        for c, s in slots:
            elig = eligible_by_subject.get(s.id, [])
            if elig:
                # Choose eligible teacher with minimal load
                chosen = min(elig, key=lambda t: load[t.id])
            else:
                # Fallback: any teacher with minimal load
                chosen = min(teachers, key=lambda t: load[t.id])

            triple = (chosen.id, c.id, s.id)
            if triple in seen:
                continue
            seen.add(triple)
            load[chosen.id] += 1
            assignments.append(TeacherClassAssignment(teacher=chosen, class_group=c, subject=s))

        # Try to ensure each teacher has at least one slot (if possible)
        total_slots = len(assignments)
        unassigned_teachers = [t for t in teachers if load[t.id] == 0]
        if unassigned_teachers and total_slots:
            # Reassign some of the easiest slots (those with multiple eligible teachers) to unassigned teachers
            # Iterate through assignments and swap where the teacher teaches that subject (or any, as fallback)
            for t in unassigned_teachers:
                swapped = False
                # First pass: find a slot where t is eligible and current teacher has higher load
                for idx, a in enumerate(assignments):
                    if t in eligible_by_subject.get(a.subject.id, []):
                        current = a.teacher
                        if load[current.id] > 1:  # keep at least one for current
                            load[current.id] -= 1
                            a.teacher = t
                            load[t.id] += 1
                            swapped = True
                            break
                if swapped:
                    continue
                # Second pass: swap any slot from a teacher with highest load
                highest = max(load, key=lambda k: load[k])
                if load[highest] > 0:
                    for idx, a in enumerate(assignments):
                        if a.teacher.id == highest:
                            load[highest] -= 1
                            a.teacher = t
                            load[t.id] += 1
                            break

        # Bulk-create, ignoring duplicates if any pre-existed
        TeacherClassAssignment.objects.bulk_create(assignments, ignore_conflicts=True, batch_size=500)

        # Report
        assigned_count = TeacherClassAssignment.objects.count()
        teachers_with_load = sum(1 for t in teachers if TeacherClassAssignment.objects.filter(teacher=t).exists())
        classes_with_full = sum(
            1 for c in classes
            if all(TeacherClassAssignment.objects.filter(class_group=c, subject=s).exists() for s in (c.subjects.all() or subjects))
        )
        self.stdout.write(self.style.SUCCESS(
            f"Assignments done. Total rows now: {assigned_count}. Teachers with >=1 assignment: {teachers_with_load}/{len(teachers)}."
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Classes with at least one teacher per subject: {classes_with_full}/{len(classes)}."
        ))
