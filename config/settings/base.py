import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env_bool(nombre, default=False):
    valor = os.environ.get(nombre)
    if valor is None:
        return default
    return valor.strip().lower() in {"1", "true", "yes", "on"}


def env_list(nombre, default=""):
    return [x.strip() for x in os.environ.get(nombre, default).split(",") if x.strip()]


# --- Núcleo ---
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "unfold",  # tiene que ir antes de django.contrib.admin
    "unfold.contrib.constance",  # estilo de Unfold para la pantalla de parámetros
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "config.estaticos.EstaticosConfig",
    "django.contrib.gis",
    "constance",
    "constance.backends.database",
    "axes",
    "apps.core",
    "apps.cuentas",
    "apps.fichas",
    "apps.publicaciones",
    "apps.transito",
    "apps.adopcion",
    "apps.reconocimiento",
    "apps.denuncias",
    "apps.contenidos",
    "apps.moderacion",
    "apps.estadisticas",
    "apps.notificaciones",
    "apps.imagenes",
    "apps.mapa",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",  # tiene que ir al final
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context.mapa",
            ],
        },
    },
]

# --- Base de datos (PostgreSQL + PostGIS) ---
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.environ.get("POSTGRES_DB", "huella"),
        "USER": os.environ.get("POSTGRES_USER", "huella"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Usuarios ---
AUTH_USER_MODEL = "cuentas.Usuario"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# El enlace de recuperación de contraseña vale 1 día, igual que el de confirmación
PASSWORD_RESET_TIMEOUT = 24 * 60 * 60

LOGIN_URL = "/cuentas/ingresar/"  # ruta literal: los tests de fichas la comparan como texto
LOGIN_REDIRECT_URL = "core:inicio"
LOGOUT_REDIRECT_URL = "core:inicio"

# django-axes tiene que ir primero en la lista de backends
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# --- Internacionalización ---
LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Ushuaia"  # los plazos son por día calendario en esta zona
USE_I18N = True
USE_TZ = True

# --- Estáticos y media ---
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

# --- Correo (solo cuentas: confirmación, recuperación y cambio de correo; RF1.2) ---
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "10"))
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-responder@localhost")

# --- Caché: ninguna (decisión del stack) / solo para reenvios, sino no se pueden controlar---
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"},
    # Guarda el freno de reenvíos de correo (cuentas). "default" no sirve: no guarda nada.
    "reenvios": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "reenvios",
    },
}

# --- Seguridad: límite de intentos de ingreso (django-axes, RNF15) ---
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_RESET_ON_SUCCESS = True
# Página de bloqueo propia (en español, con código 429).
# Usa AXES_COOLOFF_TIME: tiene que ser un timedelta.
AXES_LOCKOUT_CALLABLE = "apps.cuentas.bloqueo.respuesta_bloqueo"
# Se bloquea la combinación correo + IP, no solo la IP: quien se equivoca no deja
# afuera a los demás que comparten su conexión.
AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]
# El correo se normaliza para que mayúsculas o espacios no esquiven el bloqueo.
AXES_USERNAME_CALLABLE = "apps.cuentas.bloqueo.nombre_para_bloqueo"
# Caddy es el único proxy y deja en X-Forwarded-For solo la IP del visitante.
# Con 0, si el encabezado trae más de una IP se descarta (no se puede falsificar).
AXES_IPWARE_PROXY_COUNT = 0
AXES_IPWARE_META_PRECEDENCE_ORDER = ["HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"]

# --- Parámetros configurables (django-constance, backend de base de datos) ---
CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"
# Solo el administrador ve y cambia los parámetros. Como is_superuser sale del
# rol, "solo superusuario" equivale a "solo administrador".
CONSTANCE_SUPERUSER_ONLY = True

# Tipos de campo con rango: un valor fuera de rango se rechaza en el panel.
# Todo parámetro nuevo tiene que declarar uno como tercer valor de su línea.
_ENTERO = "unfold.widgets.UnfoldAdminIntegerFieldWidget"
_DECIMAL = "unfold.widgets.UnfoldAdminDecimalFieldWidget"


def _entero(minimo, maximo):
    return [
        "django.forms.IntegerField",
        {"min_value": minimo, "max_value": maximo, "widget": _ENTERO},
    ]


CONSTANCE_ADDITIONAL_FIELDS = {
    "dias": _entero(1, 365),
    "dias_retencion": _entero(1, 3650),
    "metros_radio": _entero(50, 1000),
    "cantidad_por_hora": _entero(1, 100),
    "distancia_phash": _entero(0, 64),
    "proporcion": [
        "django.forms.FloatField",
        {"min_value": 0, "max_value": 1, "widget": _DECIMAL},
    ],
}

CONSTANCE_CONFIG = {
    # Valores del documento unificado v4:
    "DIAS_AUSENCIA_RESPONSABLE": (
        30,
        "Días sin responsable, con alguien a cargo, antes de pasar a adopción (CU-52)",
        "dias",
    ),
    "DIAS_AVISO_VENCIMIENTO": (
        10,
        "Días antes del fin de un tránsito para avisar al hogar (CU-57)",
        "dias",
    ),
    "DIAS_PUBLICAR_VENCIMIENTO": (
        5,
        "Días antes del fin de un tránsito para publicar el animal en adopción (CU-57)",
        "dias",
    ),
    "RADIO_DOMICILIO_METROS": (
        150,
        "Radio de desplazamiento del punto de un domicilio (RNF3)",
        "metros_radio",
    ),
    "DURACION_MINIMA_TRANSITO_DIAS": (
        7,
        "Duración máxima mínima que puede declarar un hogar de tránsito (CU-06)",
        "dias",
    ),
    "DIAS_PRIMERA_SUSPENSION": (
        7,
        "Días de la primera suspensión de una cuenta (CU-59)",
        "dias",
    ),
    "DIAS_VIGENCIA_AVISTAMIENTO": (
        15,
        "Días que un avistamiento permanece vigente en la capa activa (9.2.2, RF3.7)",
        "dias",
    ),
    # Valores por definir: el de abajo es provisorio
    "MAX_PUBLICACIONES_HORA": (
        10,
        "Publicaciones por hora y por usuario (RNF15)",
        "cantidad_por_hora",
    ),
    "UMBRAL_SIMILITUD": (
        0.80,
        "Similitud coseno mínima para proponer una coincidencia (RF3.5)",
        "proporcion",
    ),
    "UMBRAL_PHASH": (
        5,
        "Distancia de Hamming máxima para considerar una foto repetida (RF2.5)",
        "distancia_phash",
    ),
    # Sale de stack.md, no del documento unificado:
    "DIAS_RETENCION_NOTIFICACIONES": (
        90,
        "Días que se conservan las notificaciones leídas",
        "dias_retencion",
    ),
    # Todavía sin parámetro (definirlos): umbrales de nivel,
    # reparto de los puntos 5/10/20/30, mínimo de días de un tránsito para sumar puntos,
    # fórmula del cupo estimado, rangos predefinidos del mapa de calor y reintentos de push.
}

# --- Push (Fase 6) ---
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_CLAIM_EMAIL = os.environ.get("VAPID_CLAIM_EMAIL", "admin@localhost")

# --- Visión (Fase 7) ---
VISION_MODEL_PATH = BASE_DIR / "models" / os.environ.get("VISION_MODEL_FILE", "mobilenetv2-12.onnx")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# --- Mapas ---
MAPA_TILES_URL = os.environ.get("MAPA_TILES_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
MAPA_TILES_ATRIBUCION = os.environ.get(
    "MAPA_TILES_ATRIBUCION",
    '&copy; Colaboradores de <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
)

# La política de uso de OpenStreetMap exige que el navegador envíe el Referer.
# El valor por defecto de Django ("same-origin") no lo manda a otros dominios.
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
