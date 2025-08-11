from .models import Notification, User

def create_notification(user, message):
    """
    Create an unread notification for a specific user.
    """
    if user and isinstance(user, User):
        Notification.objects.create(user=user, message=message)
