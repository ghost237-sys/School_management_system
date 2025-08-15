from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Import signals so they are registered
        try:
            import core.signals  # noqa: F401
        except Exception:
            # Avoid crashing app startup if migrations pending
            pass
