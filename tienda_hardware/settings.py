"""
Configuración del proyecto "tienda_hardware".

Tienda de Hardware y Componentes PC (Retail) - EVA-2 Desarrollo Backend.
Backend construido con Django REST Framework + PostgreSQL + JWT.
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# RUTAS BASE Y VARIABLES DE ENTORNO
# BASE_DIR apunta a la carpeta raíz del proyecto (donde está manage.py).
# load_dotenv() lee el archivo .env (si existe) para no dejar credenciales
# de la base de datos escritas directamente en el código.
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

# ---------------------------------------------------------------------------
# SEGURIDAD
# En producción la SECRET_KEY debe venir del .env y DEBUG debe ser False.
# ---------------------------------------------------------------------------
SECRET_KEY = os.getenv(
    'DJANGO_SECRET_KEY',
    'django-insecure-3mj&u^^)3_w0dgewh-cf3=z31+vba8*c0(dr0497iafnl9=*a+',
)
DEBUG = os.getenv('DJANGO_DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',')

# ---------------------------------------------------------------------------
# APLICACIONES INSTALADAS
# - Apps nativas de Django (admin, auth, sesiones, etc.).
# - rest_framework: Django REST Framework (API REST).
# - rest_framework_simplejwt.token_blacklist: permite invalidar refresh
#   tokens en el logout.
# - django_filters: filtros sobre los endpoints de consulta.
# - drf_spectacular: genera el esquema OpenAPI y la UI de Swagger.
# - api: nuestra aplicación con modelos, vistas y serializadores.
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'django_filters',
    'drf_spectacular',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'tienda_hardware.urls'

# ---------------------------------------------------------------------------
# PLANTILLAS
# - DIRS: carpeta "templates" del proyecto; tiene prioridad sobre las apps,
#   por eso ahí se sobrescriben las plantillas de DRF y de Swagger.
# - Context processor "datos_alumno": el footer de todas las vistas HTML
#   (tienda, API navegable y Swagger) muestra Nombre, Sección y Año.
# ---------------------------------------------------------------------------
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
                'api.context_processors.datos_alumno',
            ],
        },
    },
]

WSGI_APPLICATION = 'tienda_hardware.wsgi.application'

# ---------------------------------------------------------------------------
# BASE DE DATOS: POSTGRESQL (NO SQLite)
# Opción 1 (recomendada): DATABASE_URL -> PostgreSQL en la nube (Neon).
#   Una sola línea en el .env, por ejemplo:
#   DATABASE_URL=postgresql://usuario:clave@ep-xxxx.neon.tech/neondb?sslmode=require
#   dj_database_url la convierte al motor django.db.backends.postgresql.
#   No depende de WAMP ni de instalar nada: funciona en cualquier PC con internet.
# Opción 2 (local): sin DATABASE_URL se usan DB_ENGINE, DB_NAME, DB_USER...
#   - postgresql -> django.db.backends.postgresql (driver psycopg 3), puerto 5432
#   - mysql      -> django.db.backends.mysql (driver mysqlclient), puerto 3306
# ---------------------------------------------------------------------------
DATABASE_URL = os.getenv('DATABASE_URL')
DB_ENGINE = os.getenv('DB_ENGINE', 'postgresql')

if DATABASE_URL:
    import dj_database_url

    DATABASES = {
        # conn_max_age reutiliza la conexión (la BD está en internet).
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=60, conn_health_checks=True),
    }
    DB_ENGINE = DATABASES['default']['ENGINE'].rsplit('.', 1)[-1]
else:
    DATABASES = {
        'default': {
            'ENGINE': f'django.db.backends.{DB_ENGINE}',
            'NAME': os.getenv('DB_NAME', 'tienda_hardware'),
            'USER': os.getenv('DB_USER', 'postgres' if DB_ENGINE == 'postgresql' else 'root'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432' if DB_ENGINE == 'postgresql' else '3306'),
        }
    }

# En MySQL se usa utf8mb4 (acentos y emojis) y modo estricto de SQL.
if DB_ENGINE == 'mysql':
    DATABASES['default']['OPTIONS'] = {
        'charset': 'utf8mb4',
        'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# INTERNACIONALIZACIÓN (Chile)
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# DJANGO REST FRAMEWORK
# - Autenticación por JWT (Bearer token) y por sesión (para la API navegable
#   y el panel admin).
# - Permiso por defecto: solo lectura para anónimos; cada vista define luego
#   permisos más específicos (públicos, clientes, administradores).
# - django-filter como backend de filtros + búsqueda + ordenamiento.
# - drf-spectacular como generador del esquema OpenAPI.
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'api.pagination.PaginacionTienda',
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# ---------------------------------------------------------------------------
# JWT (djangorestframework-simplejwt)
# - access: vida corta (60 min) para consumir la API.
# - refresh: vida larga (1 día) para pedir un nuevo access.
# - ROTATE + BLACKLIST: cada refresh genera uno nuevo e invalida el anterior;
#   en el logout el refresh queda en lista negra.
# ---------------------------------------------------------------------------
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ---------------------------------------------------------------------------
# SWAGGER / OPENAPI (drf-spectacular)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    'TITLE': 'HardPC Store API',
    'DESCRIPTION': (
        'API REST de la Tienda de Hardware y Componentes PC. '
        'Autenticación JWT con claims de rol (CLIENTE / ADMIN), carro persistente, '
        'órdenes con control transaccional de stock y filtros con django-filter.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

# ---------------------------------------------------------------------------
# DATOS DEL ALUMNO (se muestran en el footer de todas las vistas HTML)
# ---------------------------------------------------------------------------
ALUMNO = {
    'nombre': 'Bryan Sandoval Morales',
    'seccion': 'IEC-N4-C1',
    'anio': '2026',  # la clave va sin "ñ": las plantillas usan {{ alumno.anio }}
}
