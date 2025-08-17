# Getting Started

## Prerequisites
- Python 3.11+
- pip, virtualenv (recommended)

## Installation
```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## Environment Variables
Set as system env vars (or with a .env loader if you prefer):
- DJANGO_SECRET_KEY
- DJANGO_DEBUG=true|false
- DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
- EMAIL_* (optional)
- SMS / Africa's Talking: AFRICASTALKING_USERNAME, AFRICASTALKING_API_KEY
- M-Pesa (Daraja): MPESA_ENVIRONMENT, MPESA_CONSUMER_KEY, MPESA_CONSUMER_SECRET, MPESA_SHORTCODE, MPESA_PASSKEY, MPESA_CALLBACK_URL

See `Analitica/settings.py` for full list and defaults.

## Database Setup
```bash
python manage.py migrate
python manage.py createsuperuser
```

## Run
```bash
python manage.py runserver
```

## Static files (production)
```bash
python manage.py collectstatic
```
