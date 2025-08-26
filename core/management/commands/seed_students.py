import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Class, Student, User


FIRST_NAMES_MALE = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles",
]
FIRST_NAMES_FEMALE = [
    "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
]


def random_birthdate(min_age=6, max_age=18):
    today = date.today()
    years = random.randint(min_age, max_age)
    # Random day within the year range
    days_offset = random.randint(0, 364)
    return date(today.year - years, 1, 1) + timedelta(days=days_offset)


class Command(BaseCommand):
    help = "Seed 30 students per existing class. Generates User accounts with role='student' and links them to Student records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--per-class", type=int, default=30,
            help="Number of students to ensure per class (default: 30)."
        )
        parser.add_argument(
            "--prefix", type=str, default="S",
            help="Admission number prefix (default: 'S')."
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Show what would be created without writing to the database."
        )

    @transaction.atomic
    def handle(self, *args, **options):
        per_class = options["per_class"]
        prefix = options["prefix"]
        dry_run = options["dry_run"]

        classes = Class.objects.all()
        if not classes.exists():
            self.stdout.write(self.style.WARNING("No classes found. Create classes first."))
            return

        created_users = 0
        created_students = 0
        planned = []

        # Pre-compute a monotonically increasing admission counter based on existing numbers
        existing_numbers = list(
            Student.objects.filter(admission_no__startswith=prefix)
            .values_list("admission_no", flat=True)
        )
        max_num = 0
        for adm in existing_numbers:
            # Extract numeric suffix
            suffix = adm[len(prefix):]
            if suffix.isdigit():
                max_num = max(max_num, int(suffix))

        counter = max_num  # will increment before use

        def next_admission_number():
            nonlocal counter
            counter += 1
            return f"{prefix}{counter:05d}"

        for c in classes:
            existing = c.students.count()
            needed = max(0, per_class - existing)
            if needed == 0:
                self.stdout.write(self.style.SUCCESS(f"{c.name}: already has {existing} students (>= {per_class})."))
                continue

            self.stdout.write(f"{c.name}: creating {needed} students to reach {per_class}.")
            for i in range(needed):
                gender = random.choice(["male", "female"])  # matches Student.gender choices usage pattern
                if gender == "male":
                    first = random.choice(FIRST_NAMES_MALE)
                else:
                    first = random.choice(FIRST_NAMES_FEMALE)
                last = random.choice(LAST_NAMES)
                admission_no = next_admission_number()
                # Deterministic unique username from admission no (avoids DB existence checks)
                username = f"stu_{admission_no.lower()}"
                email = f"{username}@example.com"
                birthdate = random_birthdate()
                phone = f"2547{random.randint(0, 99999999):08d}"

                planned.append({
                    "class": c,
                    "first": first,
                    "last": last,
                    "username": username,
                    "email": email,
                    "gender": gender,
                    "admission_no": admission_no,
                    "birthdate": birthdate,
                    "phone": phone,
                })

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no records will be created."))
            self.stdout.write(f"Would create {len(planned)} students across {classes.count()} classes.")
            for p in planned[:10]:
                self.stdout.write(f"- {p['class'].name}: {p['first']} {p['last']} ({p['admission_no']})")
            if len(planned) > 10:
                self.stdout.write(f"... and {len(planned) - 10} more")
            return

        # Fast path: bulk-create users, then bulk-create students
        if not planned:
            self.stdout.write(self.style.SUCCESS("No students needed to reach target per class."))
            return

        # Precompute a password hash once
        temp_user = User()
        temp_user.set_password("student123")
        password_hash = temp_user.password

        usernames = [p["username"] for p in planned]
        existing_usernames = set(
            User.objects.filter(username__in=usernames).values_list("username", flat=True)
        )

        users_to_create = []
        for p in planned:
            if p["username"] in existing_usernames:
                continue
            users_to_create.append(
                User(
                    username=p["username"],
                    first_name=p["first"],
                    last_name=p["last"],
                    email=p["email"],
                    role="student",
                    password=password_hash,
                )
            )

        if users_to_create:
            User.objects.bulk_create(users_to_create, batch_size=500)
            created_users += len(users_to_create)

        # Fetch all users for mapping
        user_map = {
            u.username: u for u in User.objects.filter(username__in=usernames)
        }

        students_to_create = []
        for p in planned:
            user = user_map[p["username"]]
            students_to_create.append(
                Student(
                    user=user,
                    admission_no=p["admission_no"],
                    class_group=p["class"],
                    gender=p["gender"],
                    birthdate=p["birthdate"],
                    phone=p["phone"],
                )
            )

        Student.objects.bulk_create(students_to_create, batch_size=500)
        created_students += len(students_to_create)

        self.stdout.write(self.style.SUCCESS(
            f"Created {created_students} students and {created_users} user accounts across {classes.count()} classes."
        ))
