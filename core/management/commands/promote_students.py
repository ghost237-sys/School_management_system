from django.core.management.base import BaseCommand
from core.models import Student, Class
from django.db import transaction

LOWEST_LEVEL = '1'
HIGHEST_LEVEL = '9'

class Command(BaseCommand):
    help = 'Promote students and classes to the next level, graduate highest level students, and create new lowest level classes.'

    def handle(self, *args, **options):
        with transaction.atomic():
            # Step 1: Find all unique class directions (names)
            directions = set(Class.objects.values_list('name', flat=True))

            # Step 2: Promote classes (except the highest level)
            for c in Class.objects.all():
                if c.level != HIGHEST_LEVEL:
                    new_level = str(int(c.level) + 1)
                    c.level = new_level
                    c.save()

            # Step 3: Graduate students in highest level, promote others
            for student in Student.objects.select_related('class_group'):
                if student.class_group:
                    if student.class_group.level == HIGHEST_LEVEL:
                        student.graduated = True
                        student.class_group = None  # Remove from class
                        student.save()
                    else:
                        # Find the new class with incremented level and same name
                        new_level = str(int(student.class_group.level) + 1)
                        try:
                            new_class = Class.objects.get(level=new_level, name=student.class_group.name)
                            student.class_group = new_class
                            student.save()
                        except Class.DoesNotExist:
                            self.stdout.write(self.style.WARNING(
                                f'No class found for level {new_level} and name {student.class_group.name}'))

            # Step 4: Create new lowest level classes for each direction
            for direction in directions:
                if not Class.objects.filter(level=LOWEST_LEVEL, name=direction).exists():
                    Class.objects.create(level=LOWEST_LEVEL, name=direction)
                    self.stdout.write(self.style.SUCCESS(f'Created new class: {LOWEST_LEVEL} {direction}'))

        self.stdout.write(self.style.SUCCESS('Promotion and graduation process completed.'))
