from django.utils import timezone
from datetime import datetime, time
from .models import Event

def create_event(title, date, end_date=None, all_day=True):
    """
    Create and store an event in the database.
    - title: Event title
    - date: date or datetime (for start)
    - end_date: date or datetime (optional)
    - all_day: bool
    """
    # Ensure start is timezone-aware datetime
    if isinstance(date, datetime):
        start_dt = timezone.make_aware(date) if timezone.is_naive(date) else date
    else:
        # If a date, combine with midnight
        start_dt = timezone.make_aware(datetime.combine(date, time.min))
    end_dt = None
    if end_date:
        if isinstance(end_date, datetime):
            end_dt = timezone.make_aware(end_date) if timezone.is_naive(end_date) else end_date
        else:
            end_dt = timezone.make_aware(datetime.combine(end_date, time.max))
    return Event.objects.create(title=title, start=start_dt, end=end_dt, all_day=all_day)
