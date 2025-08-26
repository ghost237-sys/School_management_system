from django.apps import AppConfig
from django.db import connection


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

        # Put SQLite into WAL mode to reduce writer lock contention and
        # ensure foreign keys are enforced. Safe to run repeatedly.
        try:
            if connection.vendor == 'sqlite':
                with connection.cursor() as cursor:
                    cursor.execute("PRAGMA journal_mode=WAL;")
                    cursor.execute("PRAGMA foreign_keys=ON;")
        except Exception:
            # Do not block app startup if PRAGMAs fail (e.g., non-SQLite DB)
            pass
