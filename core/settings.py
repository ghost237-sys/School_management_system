import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = 'replace-this-with-a-secure-key'
DEBUG = True
ALLOWED_HOSTS = []

# --- M-Pesa Daraja API Credentials ---
MPESA_CONSUMER_KEY = 'EbgLks2JrZyEnGAfe0lqC9rKHPXutqG9VdYptaVdNZTUmQ2d'
MPESA_CONSUMER_SECRET = 'fBm0Nywpvr5wGqQ20rTaTZGrWXcThUR2OoIJXFpUzj8IXt7ZTYzZCcaeGSDHJIRX'
MPESA_SECURITY_CREDENTIAL = 'OochZUouFckkb3ZOoFMWH2iVESIECTD6fUI46ZVykffMP4CCcFjXLfpGd6StLWpd+u8BsCJ2EYKNPlYQeH5wQxIw3u+ziMPumnRdZfGMSGQnyx76nLqwsJDe8leMaMyGpbcRYrdKU5C3JqWGD5BdoBdhg4ByfI9ds/T5y/mRBUzCLsHUTbZT6DgvaK2Ln8P5mg4Jva9xCGf/hKCp3fN1VzGW9Cn6+5+6GJPVrzdBjx+XbWTvBOhpfTlZ+ko3IqJL81h8Bk9OlXEd0LyjbKVHmlfvphdafFfYsAV6wOACEclJmyH3sTZO2YXKQTCGGsQi6bdkGPvSBnGs5bsfBC+KeA=='
MPESA_SHORTCODE = '400200'
MPESA_PASSKEY = '<YOUR_PASSKEY_FROM_DARAJA_PORTAL>'
MPESA_INITIATOR_NAME = '<YOUR_INITIATOR_NAME>'
MPESA_ACCOUNT_NUMBER = '710092'
MPESA_ENVIRONMENT = 'sandbox'  # or 'production' for live
# --- End M-Pesa Credentials ---

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
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

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'
