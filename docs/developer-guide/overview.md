# Developer Guide

## Project Layout
- `Analitica/` – settings, URLs, WSGI/ASGI
- `core/` – main app: models, views, templates (`core/templates/`), services
- `landing/` – public site pages
- `static/`, `staticfiles/`, `media/`
- `scripts/` – utilities (e.g., `dedupe_user_emails.py`)

## Settings Highlights (`Analitica/settings.py`)
- Templates dir: `core/templates`
- Custom user model: `core.User`
- Nairobi timezone, security headers, cookie settings
- Logging with PII redaction (phones, M-Pesa receipts)
- SMS (Africa's Talking) and M-Pesa Daraja configs via env vars

## URLs and Views
- Root: `Analitica/urls.py`
- Ensure all feature URLs are included (watch for NoReverseMatch if a module isn't included).

## Management Commands
- Promotions handled by `promote_students` (invoked from admin academic years).

## Services
- `core/services/timetable_scheduler.py`

## Local Dev
```bash
python manage.py migrate
python manage.py runserver
```

## Testing M-Pesa
- See `simulate_mpesa.py` and `test_mpesa_callback.py`.
- Ensure the phone matches an existing student with a current term and fee assignment.
