from django.core.management.base import BaseCommand
from django.db.models import Count
from core.models import User

class Command(BaseCommand):
    help = 'Finds and lists users with duplicate email addresses.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Searching for duplicate emails..."))
        duplicates = (
            User.objects.values('email')
            .annotate(email_count=Count('email'))
            .filter(email_count__gt=1)
        )

        if not duplicates:
            self.stdout.write(self.style.SUCCESS("No duplicate emails found."))
            return

        self.stdout.write(self.style.WARNING("Found duplicate emails:"))
        for item in duplicates:
            email = item['email']
            count = item['email_count']
            self.stdout.write(f"- Email: '{email}' is used by {count} users.")
            users_with_email = User.objects.filter(email=email)
            for user in users_with_email:
                self.stdout.write(f"  - User ID: {user.id}, Username: {user.username}, Role: {user.role}")
