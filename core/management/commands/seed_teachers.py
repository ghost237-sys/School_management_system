import random
from typing import List

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import User, Teacher, Department, Subject, Class

FIRST_NAMES_MALE = [
    "Peter", "Paul", "Mark", "Daniel", "Kevin", "Brian", "George", "Anthony", "Samuel", "Steven",
]
FIRST_NAMES_FEMALE = [
    "Alice", "Grace", "Nancy", "Caroline", "Lucy", "Agnes", "Irene", "Dorothy", "Ruth", "Sarah",
]
LAST_NAMES = [
    "Otieno", "Kariuki", "Mwangi", "Njoroge", "Mutiso", "Ouma", "Wanjiru", "Kimani", "Achieng", "Omondi",
]


class Command(BaseCommand):
    help = "Seed teacher users and Teacher profiles. Optionally assign as class teachers where vacant."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count", type=int, default=20,
            help="Number of teacher accounts to create (default: 20)."
        )
        parser.add_argument(
            "--assign-class-teachers", action="store_true",
            help="Assign newly created teachers to classes that lack a class_teacher."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        count: int = options["count"]
        assign_ct: bool = options["assign_class_teachers"]

        departments: List[Department] = list(Department.objects.all())
        subjects: List[Subject] = list(Subject.objects.all())
        classes: List[Class] = list(Class.objects.all())

        if count <= 0:
            self.stdout.write(self.style.WARNING("Count must be > 0"))
            return

        # Determine starting indexes to keep usernames/staff ids unique
        existing_teachers = Teacher.objects.count()
        start_index = existing_teachers + 1

        planned = []
        for i in range(count):
            gender = random.choice(["male", "female"])
            first = random.choice(FIRST_NAMES_MALE if gender == "male" else FIRST_NAMES_FEMALE)
            last = random.choice(LAST_NAMES)

            idx = start_index + i
            username = f"tchr_{idx:04d}"
            email = f"{username}@example.com"
            staff_id = f"STF{idx:05d}"
            tsc_number = f"TSC{idx:06d}"
            phone = f"2547{random.randint(0, 99999999):08d}"

            dept = random.choice(departments) if departments else None
            # pick 1-3 random subjects if available
            subj_choices: List[Subject] = random.sample(subjects, k=min(len(subjects), random.randint(1, 3))) if subjects else []

            planned.append({
                "first": first,
                "last": last,
                "gender": gender,
                "username": username,
                "email": email,
                "staff_id": staff_id,
                "tsc_number": tsc_number,
                "phone": phone,
                "department": dept,
                "subjects": subj_choices,
            })

        # Prepare password hash once
        temp = User()
        temp.set_password("teacher123")
        password_hash = temp.password

        # Create Users in bulk (skip existing usernames)
        usernames = [p["username"] for p in planned]
        existing_usernames = set(User.objects.filter(username__in=usernames).values_list("username", flat=True))

        users_to_create = []
        for p in planned:
            if p["username"] in existing_usernames:
                continue
            users_to_create.append(User(
                username=p["username"],
                first_name=p["first"],
                last_name=p["last"],
                email=p["email"],
                role="teacher",
                password=password_hash,
            ))
        if users_to_create:
            User.objects.bulk_create(users_to_create, batch_size=500)
        self.stdout.write(self.style.SUCCESS(f"Created {len(users_to_create)} user accounts."))

        # Map usernames to users
        user_map = {u.username: u for u in User.objects.filter(username__in=usernames)}

        # Create Teacher profiles in bulk (skip if profile already exists for user)
        existing_teacher_user_ids = set(Teacher.objects.filter(user_id__in=[u.id for u in user_map.values()]).values_list("user_id", flat=True))
        teachers_to_create = []
        for p in planned:
            u = user_map[p["username"]]
            if u.id in existing_teacher_user_ids:
                continue
            teachers_to_create.append(Teacher(
                user=u,
                tsc_number=p["tsc_number"],
                staff_id=p["staff_id"],
                phone=p["phone"],
                gender=p["gender"],
                department=p["department"],
            ))
        if teachers_to_create:
            Teacher.objects.bulk_create(teachers_to_create, batch_size=500)
        self.stdout.write(self.style.SUCCESS(f"Created {len(teachers_to_create)} teacher profiles."))

        # Attach M2M subjects
        teacher_map = {t.user.username: t for t in Teacher.objects.select_related("user").filter(user__username__in=usernames)}
        attach_count = 0
        for p in planned:
            t = teacher_map.get(p["username"])  # may be None if existed
            if not t:
                continue
            if p["subjects"]:
                t.subjects.set(p["subjects"])  # single write per teacher
                attach_count += 1
        self.stdout.write(self.style.SUCCESS(f"Assigned subjects for {attach_count} teachers."))

        # Optionally assign class_teacher for classes without one
        if assign_ct and classes:
            vacant_classes = [c for c in classes if not c.class_teacher_id]
            # pick some of our newly created teachers to assign
            created_teachers = [teacher_map.get(p["username"]) for p in planned]
            created_teachers = [t for t in created_teachers if t]
            random.shuffle(created_teachers)
            assigned = 0
            for c, t in zip(vacant_classes, created_teachers):
                c.class_teacher = t
                c.save(update_fields=["class_teacher"])  # one update per class
                assigned += 1
            if assigned:
                self.stdout.write(self.style.SUCCESS(f"Assigned {assigned} class teachers to vacant classes."))
            else:
                self.stdout.write("No vacant classes or no new teachers to assign.")

        self.stdout.write(self.style.SUCCESS("Done."))
