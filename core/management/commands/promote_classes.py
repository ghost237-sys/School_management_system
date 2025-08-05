from django.core.management.base import BaseCommand
from core.models import Class, PromotionLog
from django.utils import timezone

class Command(BaseCommand):
    help = 'Promotes all classes to the next level at the end of the academic year, only once per year.'

    def handle(self, *args, **options):
        MAX_LEVEL = 12  # Change this to your school's max level if needed
        promoted_count = 0
        now = timezone.now()
        current_year = now.year

        # Get or create PromotionLog
        log, _ = PromotionLog.objects.get_or_create(id=1)
        last_promoted_year = log.last_promoted_year

        if current_year <= last_promoted_year:
            self.stdout.write(self.style.WARNING(f'Classes have already been promoted for {current_year}. No action taken.'))
            return
        # Only run after academic year ends (e.g., after August 1)
        if now.month < 8:
            self.stdout.write(self.style.WARNING('It is not yet the end of the academic year. No classes promoted.'))
            return
        for c in Class.objects.all():
            try:
                current_level = int(c.level)
            except (ValueError, TypeError):
                self.stdout.write(self.style.ERROR(f'Class {c.name} has non-integer level: {c.level}'))
                continue
            if current_level >= MAX_LEVEL:
                self.stdout.write(self.style.WARNING(f'Class {c.name} already at or above max level ({MAX_LEVEL}).'))
                continue
            c.level = str(current_level + 1)
            c.save()
            promoted_count += 1
            self.stdout.write(self.style.SUCCESS(f'Promoted {c.name} to level {c.level}'))
        log.last_promoted_year = current_year
        log.save()
        self.stdout.write(self.style.SUCCESS(f'Promotion complete. {promoted_count} classes promoted for {current_year}.'))
