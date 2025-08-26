# School Management System

A Django-based platform to manage students, classes, fees, exams, messaging, calendars, and analytics.

## Quickstart

1) Create a virtual environment and install dependencies

```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

2) Set environment variables (see `Analitica/settings.py` for the full list)

- DJANGO_SECRET_KEY
- DJANGO_DEBUG=true|false
- DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
- Optional: Email, Africa's Talking (SMS), M‑Pesa Daraja credentials

3) Initialize the database and run the server

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

4) Production static files

```bash
python manage.py collectstatic
```

## Documentation

Full docs are available under `docs/` and can be served locally with MkDocs:

```bash
pip install -r docs/requirements-docs.txt
mkdocs serve
```

Then open http://127.0.0.1:8000 in your browser.

Key topics:
- Getting Started
- User Guides (Admin, Teacher)
- Developer Guide
- Integrations (M‑Pesa)
- Troubleshooting

## Email (SMTP) setup — Gmail

Use Gmail SMTP with an App Password to send real emails from the system. The project reads these values from environment variables (see `Analitica/settings.py`).

Run this in PowerShell (Windows) before starting the server:

```powershell
$env:EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend';
$env:EMAIL_HOST='smtp.gmail.com';
$env:EMAIL_PORT='587';
$env:EMAIL_USE_TLS='true';
$env:EMAIL_HOST_USER='sevenforksprimaryschool@gmail.com';
$env:EMAIL_HOST_PASSWORD='jwuw grhy epvt lqcf';  # Your Gmail App Password
$env:DEFAULT_FROM_EMAIL='sevenforksprimaryschool@gmail.com';
"Email env configured: BACKEND=$env:EMAIL_BACKEND, HOST=$env:EMAIL_HOST, USER=$env:EMAIL_HOST_USER, FROM=$env:DEFAULT_FROM_EMAIL"
```

Notes:
- You must create a Gmail App Password (not your normal password). See Google Account → Security → App passwords.
- Never commit secrets to source control. Prefer system/service environment variables in production.
