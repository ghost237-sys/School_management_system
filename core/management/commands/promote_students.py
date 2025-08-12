from django.core.management.base import BaseCommand
from core.models import Student, Class
from django.db import transaction

LOWEST_LEVEL = '1'
HIGHEST_LEVEL = '9'

class Command(BaseCommand):
    help = 'Promote students and classes to the next level, graduate highest level students, and create new lowest level classes.'

    def handle(self, *args, **options):
        with transaction.atomic():
            # Step 1: Prepare target streams for lowest level (Grade 1)
            target_streams = ['East', 'West', 'North', 'South']

            # Step 2: Promote classes (except the highest level)
            for c in Class.objects.all():
                if c.level != HIGHEST_LEVEL:
                    old_level = c.level
                    new_level = str(int(c.level) + 1)
                    # Update class name if it starts with 'Grade {old_level}'
                    import re
                    match = re.match(r'^Grade\s+(\d+)(.*)$', c.name)
                    if match:
                        suffix = match.group(2)
                        c.name = f"Grade {new_level}{suffix}"
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
                        # Find the new class with incremented level and updated name
                        new_level = str(int(student.class_group.level) + 1)
                        import re
                        match = re.match(r'^Grade\s+(\d+)(.*)$', student.class_group.name)
                        if match:
                            suffix = match.group(2)
                            promoted_name = f"Grade {new_level}{suffix}"
                        else:
                            promoted_name = student.class_group.name
                        try:
                            new_class = Class.objects.get(level=new_level, name=promoted_name)
                            student.class_group = new_class
                            student.save()
                        except Class.DoesNotExist:
                            self.stdout.write(self.style.WARNING(
                                f'No class found for level {new_level} and name {promoted_name}'))

            # Step 4: Create only the four Grade 1 streams (East/West/North/South)
            for stream in target_streams:
                name = f"Grade {LOWEST_LEVEL} {stream}"
                if not Class.objects.filter(level=LOWEST_LEVEL, name=name).exists():
                    Class.objects.create(level=LOWEST_LEVEL, name=name)
                    self.stdout.write(self.style.SUCCESS(f'Created new class: {name}'))

        self.stdout.write(self.style.SUCCESS('Promotion and graduation process completed.'))
