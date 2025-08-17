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
