"""
Django settings for eventflow_backend project.
Projet EVENTFLOW — FORCE-N 2026, groupe 2.
"""

from pathlib import Path
from datetime import timedelta
from decouple import config, Csv
import dj_database_url

# ------------------------------------------------------------------
# BASE
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())
ALLOWED_HOSTS += ['.onrender.com']  # production Autoriser tous les sous-domaines Render

# ------------------------------------------------------------------
# APPLICATIONS
# ------------------------------------------------------------------
INSTALLED_APPS = [
    # Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Tierces parties
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_spectacular',

    # Apps EVENTFLOW
    'apps.accounts',
    'apps.events',
    'apps.registrations',
    'apps.tickets',
    'apps.payments',
    'apps.attendance',
    'apps.certificates',
    'apps.notifications',
    'apps.dashboards',
    'apps.supervision',
]

# ------------------------------------------------------------------
# MIDDLEWARE
# ------------------------------------------------------------------
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',      #en production pour servir les fichiers statiques, le niveau gratuit de Render n'inclut pas de CDN
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
ROOT_URLCONF = 'eventflow_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'eventflow_backend.wsgi.application'

# ------------------------------------------------------------------
# BASE DE DONNÉES — PostgreSQL
# ------------------------------------------------------------------

# 1. Configuration locale par défaut (PostgreSQL via decouple)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME', default='eventflow_db'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='127.0.0.1'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# 2. En production (Render/Neon), DATABASE_URL écrase la config locale
DATABASE_URL = config('DATABASE_URL', default=None)
if DATABASE_URL:
    DATABASES['default'] = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
    
# ------------------------------------------------------------------
# AUTHENTIFICATION
# ------------------------------------------------------------------
AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ------------------------------------------------------------------
# INTERNATIONALISATION
# ------------------------------------------------------------------
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Dakar'
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------
# FICHIERS STATIQUES ET MÉDIAS
# ------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
# Dossier configurable : en production, pointer vers un disque persistant
# (Render Disk monté sur /var/data par exemple) pour éviter la perte des
# fichiers à chaque redéploiement.
MEDIA_ROOT = Path(config('MEDIA_ROOT', default=str(BASE_DIR / 'media')))

# ------------------------------------------------------------------
# STOCKAGE MÉDIA EXTERNE (S3-compatible, optionnel)
# ------------------------------------------------------------------
# Dès que AWS_STORAGE_BUCKET_NAME est défini, les médias (couvertures
# d'événements, PDF de certificats) sont stockés sur un service compatible
# S3 au lieu du disque local — indispensable sur le plan gratuit Render,
# dont le disque est éphémère.
#
# Fournisseurs compatibles (tous avec une offre gratuite) :
#   - Supabase Storage : https://<projet>.supabase.co/storage/v1/s3
#   - Cloudflare R2    : https://<account-id>.r2.cloudflarestorage.com
#   - Backblaze B2     : https://s3.<region>.backblazeb2.com
#   - Amazon S3 / MinIO
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='')
AWS_S3_ENDPOINT_URL = config('AWS_S3_ENDPOINT_URL', default='')
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='auto')
# URL publique de base du bucket (ex: https://pub-xxx.r2.dev). Si vide, des
# URL signées (expirantes) sont générées : pratique pour un bucket privé.
AWS_S3_PUBLIC_URL = config('AWS_S3_PUBLIC_URL', default='')
AWS_S3_QUERYSTRING_EXPIRE = config('AWS_S3_QUERYSTRING_EXPIRE', default=3600, cast=int)

if AWS_STORAGE_BUCKET_NAME:
    if not (AWS_S3_ENDPOINT_URL and AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY):
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(
            "Stockage S3 incomplet : renseignez AWS_S3_ENDPOINT_URL, "
            "AWS_ACCESS_KEY_ID et AWS_SECRET_ACCESS_KEY "
            "(ou retirez AWS_STORAGE_BUCKET_NAME pour revenir au disque local)."
        )
    STORAGES['default'] = {'BACKEND': 'common.storage.s3.S3Storage'}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ------------------------------------------------------------------
# EMAIL (dev : console)
# ------------------------------------------------------------------
INSTALLED_APPS += ['anymail']

EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
ANYMAIL = {"BREVO_API_KEY": config("BREVO_API_KEY", default="")}
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='EVENTFLOW <noreply@eventflow.sn>')

# ✅ Lire les autres paramètres SMTP depuis le .env
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=25, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=False, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=10, cast=int)

# ------------------------------------------------------------------
# DRF + JWT
# ------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'common.exceptions.handlers.custom_exception_handler',
    # ⚠️ Désactivé : DRF utilise par défaut `?format=` pour la négociation de
    # contenu. Or l'API expose `?format=ONLINE|IN_PERSON` (EventFilter) ; sans
    # ce réglage, DRF intercepte le paramètre et renvoie 404 (format inconnu).
    'URL_FORMAT_OVERRIDE': None,
    # ✅ UN SEUL DEFAULT_THROTTLE_RATES (fusion des deux)
    'DEFAULT_THROTTLE_CLASSES': [],
    # ⚠️ Chaque scope utilisé par une vue DOIT être déclaré ici, sinon DRF
    # lève ImproperlyConfigured (erreur 500) au premier appel.
    'DEFAULT_THROTTLE_RATES': {
        # Authentification (par IP / utilisateur)
        'auth_register': config('AUTH_REGISTER_RATE', default='10/hour'),
        'auth_verify': config('AUTH_VERIFY_RATE', default='30/hour'),
        'auth_email': config('AUTH_EMAIL_RATE', default='5/hour'),
        'auth_login': config('AUTH_LOGIN_RATE', default='10/min'),
        'auth_refresh': config('AUTH_REFRESH_RATE', default='30/min'),
        'auth_logout': config('AUTH_LOGOUT_RATE', default='30/min'),
        'auth_password': config('AUTH_PASSWORD_RATE', default='5/hour'),
        # Authentification (par email ciblé, cf. common/throttles.py)
        'auth_login_email': config('AUTH_LOGIN_EMAIL_RATE', default='5/min'),
        'auth_email_target': config('AUTH_EMAIL_TARGET_RATE', default='5/hour'),
        # Paiements
        'payment_initiate': config('PAYMENT_INITIATE_RATE', default='10/min'),
        'payment_action': config('PAYMENT_ACTION_RATE', default='20/min'),
        # Supervision
        'supervision_read': config('SUPERVISION_READ_RATE', default='300/min'),
        'supervision_action': config('SUPERVISION_ACTION_RATE', default='30/min'),
        # Attendance
        'attendance_checkin': '60/min',
        'attendance_qr': '120/min',
        # Certificates
        'certificate_verify': '30/min',
        'certificate_generate': config('CERTIFICATE_GENERATE_RATE', default='10/hour'),
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'EVENTFLOW API',
    'DESCRIPTION': "API de gestion d'événements — Projet FORCE-N 2026",
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# ------------------------------------------------------------------
# PAYMENT
# ------------------------------------------------------------------
PAYMENT_DEFAULT_CURRENCY = config("PAYMENT_DEFAULT_CURRENCY", default="XOF")
# Fail-closed : la simulation de paiement est désactivée par défaut et
# interdite en production. Elle ne doit jamais permettre de marquer un
# paiement comme réussi sans encaissement réel.
PAYMENT_DEVELOPMENT_ENABLED = config(
    "PAYMENT_DEVELOPMENT_ENABLED",
    default=False,
    cast=bool,
)
if PAYMENT_DEVELOPMENT_ENABLED and not DEBUG:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "PAYMENT_DEVELOPMENT_ENABLED doit être False lorsque DEBUG=False. "
        "La simulation de paiement est réservée au développement local."
    )

# ------------------------------------------------------------------
# ADMIN / DOCUMENTATION / QR
# ------------------------------------------------------------------
# Chemin personnalisable de l'admin Django (doit finir par "/").
ADMIN_URL = config("ADMIN_URL", default="admin/")

# Documentation OpenAPI : désactivée par défaut hors DEBUG, car elle décrit
# toute la surface d'attaque de l'API.
API_DOCS_ENABLED = config("API_DOCS_ENABLED", default=DEBUG, cast=bool)

# Clé HMAC dédiée à la signature des QR codes. Si elle n'est pas définie,
# le code retombe sur SECRET_KEY (compatibilité ascendante). Recommandé :
# une valeur distincte de SECRET_KEY.
QR_SIGNING_KEY = config("QR_SIGNING_KEY", default=SECRET_KEY)

# ------------------------------------------------------------------
# CORS (pour Angular)
# ------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default=(
        'http://localhost:4200,'
        'http://127.0.0.1:4200,'
        'http://localhost:53772,'
        'http://127.0.0.1:53772'
    ),
    cast=Csv()
)

CORS_ALLOW_CREDENTIALS = True

# ================================================================
# ATTENDANCE
# ================================================================
# Nombre de minutes avant le début de l'événement pendant lesquelles
# le check-in est déjà ouvert.
ATTENDANCE_CHECK_IN_OPENS_BEFORE_MINUTES = config(
    "ATTENDANCE_CHECK_IN_OPENS_BEFORE_MINUTES",
    default=120,
    cast=int,
)

# ------------------------------------------------------------------
# SÉCURITÉ (production)
# ------------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

    # ------------------------------------------------------------------
# CERTIFICATES
# ------------------------------------------------------------------
FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:4200")
CERTIFICATE_VERIFY_URL_BASE = config(
    "CERTIFICATE_VERIFY_URL_BASE",
    default=f"{FRONTEND_URL}/verify",
)

# production
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')   