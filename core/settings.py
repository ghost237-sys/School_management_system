import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = 'replace-this-with-a-secure-key'
DEBUG = True
ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '8c31c7ea20f2.ngrok-free.app',
    '08d4e7a36369.ngrok-free.app',  # <-- Added new ngrok domain
    '469684394867.ngrok-free.app',  # <-- Current ngrok domain
    '.ngrok-free.app',  # <-- Allow any ngrok subdomain
]

CSRF_TRUSTED_ORIGINS = [
    'https://8c31c7ea20f2.ngrok-free.app',
    'https://08d4e7a36369.ngrok-free.app',  # <-- Added new ngrok domain
    'https://469684394867.ngrok-free.app',  # <-- Current ngrok domain
    'https://*.ngrok-free.app',  # <-- Trust any ngrok subdomain for CSRF
]

MPESA_CONSUMER_KEY = 'EXGFqWiPKTmwUrCGfKmHbUzj43Ikge7ekz5GVSbdzAk37L0j'
MPESA_CONSUMER_SECRET = 'lOjIKLlnhiHXxFRDkfkv9m8pm80ZJhNGQpcuuq3ktdyx9GAKk8pP8Aw4VlLRVnU1'
MPESA_SECURITY_CREDENTIAL = 'MAVwHpewRUL/DCazjHl9tFC50Aa+lBq1wusfpEYL4118SkIxFa9fttEN24kO1wjKlhl3msXzX9jGuK0ra2W9XNVgRgAA4p1DzW8eAtg4OKKoMAzZ25GXBuDJFaniFsokK7oBouxwq9OWuS4M8g2aYb+6RGO3+vEYUvT3a6M8n5KD8wGk7wGlOXlHKfICEGcaWHb9XMEhaix9l97leFQePUS1XXiKVhlXTTb1Qey9xkCzZXOXbtY4cz/qMT4wKXlwzm4aCpUYJVajrZCRYsZv6L8H/s331f9D/PX+DQ1oLjwjVGptx8SwfZrYOe9s3pHpgyTw4dUyou5Rub+OSwQETg=='
MPESA_SHORTCODE = '174379'
MPESA_PASSKEY = 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919'
MPESA_INITIATOR_NAME = '<YOUR_INITIATOR_NAME>'
MPESA_ACCOUNT_NUMBER = '710092'
MPESA_ENVIRONMENT = 'sandbox'  # or 'production' for live
# --- End M-Pesa Credentials ---

# Public callback URL used by Safaricom for STK push callbacks
# Ensure this matches your active tunnel/domain
MPESA_CALLBACK_URL = 'https://469684394867.ngrok-free.app/mpesa-callback/'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
    'landing',
    'crispy_forms',
    'crispy_bootstrap5',
]

# Email settings (Gmail SMTP for real email delivery)
EMAIL_ENABLED = True  # Set to False to disable all outgoing emails
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'sevenforksprimaryschool@gmail.com')
EMAIL_HOST_PASSWORD = 'dfcd rzjc plga ltre'  # App password set directly for immediate fix
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)

# Twilio SMS settings
SMS_ENABLED = True  # Set to False to disable all outgoing SMS
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '')

# Africa's Talking SMS settings
# Prefer using environment variables; fall back to sandbox defaults for development.
AFRICASTALKING_USERNAME = os.environ.get('AFRICASTALKING_USERNAME', 'sandbox')
AFRICASTALKING_API_KEY = os.environ.get('AFRICASTALKING_API_KEY', 'atsk_71b95d4bf13dca4dc54611eac4532396b47482939ee43c6da450a4311693086b935ad13e')
AFRICASTALKING_SENDER_ID = os.environ.get('AFRICASTALKING_SENDER_ID', '')  # leave blank in sandbox

# Default country code for normalizing local phone numbers to E.164
# Example: '254' for Kenya
DEFAULT_SMS_COUNTRY_CODE = os.environ.get('DEFAULT_SMS_COUNTRY_CODE', '254')

# Fallback school name used in notifications when SiteSettings is not available
SCHOOL_NAME = os.environ.get('SCHOOL_NAME', 'Your School')

# Use custom user model
AUTH_USER_MODEL = 'core.User'


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Ensure Django respects HTTPS scheme when behind ngrok's proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'core', 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media (user uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# Ensure all logs are visible in terminal during development
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'formatters': {
        'simple': {
            'format': '[{levelname}] {message}',
            'style': '{',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
