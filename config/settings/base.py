"""Configuración común a todos los entornos.

Todo lo que cambia según el entorno viene de variables de entorno
(ver .env.example). Nada aquí depende del proveedor de hosting.
"""

from pathlib import Path

import environ

# config/settings/base.py -> raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

# En local se lee .env; en Koyeb no existe el archivo y las variables
# vienen del panel del servicio.
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    environ.Env.read_env(_env_file)

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# --- Aplicaciones ---------------------------------------------------------

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "crispy_forms",
    "crispy_bootstrap5",
    "django_htmx",
    "simple_history",
]

LOCAL_APPS = [
    "core",
    "academico",
    "ingresos",
    "gastos",
    "cambio",
    "reportes",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Base de datos --------------------------------------------------------
# Sin valor por defecto a propósito: no queremos caer en SQLite sin darnos
# cuenta (select_for_update y varias restricciones se comportan distinto).

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = 60
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Autenticación --------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "login"

# --- Idioma, zona horaria y formatos -------------------------------------

LANGUAGE_CODE = env("LANGUAGE_CODE", default="es-ve")
TIME_ZONE = env("TIME_ZONE", default="America/Caracas")
USE_I18N = True
USE_TZ = True
USE_THOUSAND_SEPARATOR = True

# --- Archivos estáticos ---------------------------------------------------
# Edumia no guarda archivos subidos (D-05): no hay MEDIA_ROOT.

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Formularios ----------------------------------------------------------

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# --- Reglas de negocio configurables -------------------------------------

# D-13: desviación (en %) del monto esperado a partir de la cual se pide confirmación
UMBRAL_DESVIACION_MONTO = 20
