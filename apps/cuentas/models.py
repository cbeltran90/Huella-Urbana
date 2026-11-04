import hashlib

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.contrib.gis.db.models import PointField
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class Rol(models.TextChoices):
    REGISTRADO = "registrado", "Registrado"
    MODERADOR = "moderador", "Moderador"
    ADMINISTRADOR = "administrador", "Administrador"


class EstadoCuenta(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente de confirmación"
    ACTIVA = "activa", "Activa"
    ELIMINADA = "eliminada", "Eliminada"


def normalizar_email(email):
    """Minúsculas y sin espacios: se usa al guardar, al buscar y al calcular el hash."""
    return (email or "").strip().lower()


def hash_email(email):
    """SHA-256 del correo normalizado (sirve para controlar reincidencias, RF1.3)."""
    return hashlib.sha256(normalizar_email(email).encode("utf-8")).hexdigest()


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, email):
        # El inicio de sesión no distingue mayúsculas en el correo.
        return self.get(email__iexact=normalizar_email(email))

    def _crear(self, email, nombre_usuario, password, **campos):
        email = normalizar_email(email)
        if not email:
            raise ValueError("El correo es obligatorio.")
        if not nombre_usuario:
            raise ValueError("El nombre de usuario es obligatorio.")
        usuario = self.model(email=email, nombre_usuario=nombre_usuario, **campos)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, nombre_usuario, password=None, **campos):
        campos.setdefault("is_staff", False)
        campos.setdefault("is_superuser", False)
        return self._crear(email, nombre_usuario, password, **campos)

    def create_superuser(self, email, nombre_usuario, password=None, **campos):
        campos.setdefault("is_staff", True)
        campos.setdefault("is_superuser", True)
        campos.setdefault("estado_cuenta", EstadoCuenta.ACTIVA)
        campos.setdefault("rol", Rol.ADMINISTRADOR)
        if campos["is_staff"] is not True:
            raise ValueError("Un superusuario debe tener is_staff=True.")
        if campos["is_superuser"] is not True:
            raise ValueError("Un superusuario debe tener is_superuser=True.")
        return self._crear(email, nombre_usuario, password, **campos)


class Usuario(AbstractUser):
    """Usuario del sistema (DER: Usuario). Se identifica con el correo; no tiene username."""

    username = None
    email = models.EmailField("correo electrónico", unique=True)
    email_hash = models.CharField(max_length=64, blank=True)
    nombre_usuario = models.CharField("nombre de usuario", max_length=150)
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.REGISTRADO)
    es_organizacion = models.BooleanField(default=False)
    es_zoonosis = models.BooleanField(default=False)
    estado_cuenta = models.CharField(
        max_length=20, choices=EstadoCuenta.choices, default=EstadoCuenta.PENDIENTE
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)
    acepto_condiciones_at = models.DateTimeField(null=True, blank=True)

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nombre_usuario"]

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        constraints = [
            models.UniqueConstraint(
                Lower("nombre_usuario"),
                name="usuario_nombre_usuario_unico_ci",
                violation_error_message="Nombre ya usado",
            ),
        ]

    def __str__(self):
        return self.nombre_usuario

    def save(self, *args, **kwargs):
        self.email = normalizar_email(self.email)
        self.email_hash = hash_email(self.email)
        # is_active se deriva de estado_cuenta: solo una cuenta activa puede entrar.
        self.is_active = self.estado_cuenta == EstadoCuenta.ACTIVA
        # El acceso al panel y los permisos totales se derivan del rol (CU-07).
        self.is_staff = self.rol in (Rol.MODERADOR, Rol.ADMINISTRADOR)
        self.is_superuser = self.rol == Rol.ADMINISTRADOR
        campos = kwargs.get("update_fields")
        if campos is not None:
            derivados = set(campos)
            if "estado_cuenta" in campos:
                derivados.add("is_active")
            if "rol" in campos:
                derivados.update({"is_staff", "is_superuser"})
            kwargs["update_fields"] = derivados
        super().save(*args, **kwargs)


class SancionQuerySet(models.QuerySet):
    def vigentes(self):
        """Las sanciones que hoy rigen: ya empezaron, no se levantaron y no vencieron."""
        ahora = timezone.now()
        return self.filter(revocada_en__isnull=True, inicio__lte=ahora).filter(
            models.Q(fin__isnull=True) | models.Q(fin__gt=ahora)
        )


class Sancion(models.Model):
    """Suspensión de una cuenta (CU-59).

    La persona sigue pudiendo entrar, pero con los permisos de un visitante.
    Guarda el hash del correo para que una suspensión permanente siga valiendo aunque la
    cuenta se elimine y la persona vuelva a registrarse con el mismo correo (RF1.3).
    """

    class Tipo(models.TextChoices):
        TEMPORAL = "temporal", "Suspensión temporal"
        PERMANENTE = "permanente", "Suspensión permanente"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sanciones",
    )
    email_hash = models.CharField(max_length=64, db_index=True)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    motivo = models.TextField()
    inicio = models.DateTimeField(default=timezone.now)
    # Vacío en la suspensión permanente.
    fin = models.DateTimeField(null=True, blank=True)
    aplicada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sanciones_aplicadas",
    )
    revocada_en = models.DateTimeField(null=True, blank=True)
    revocada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sanciones_levantadas",
    )

    objects = SancionQuerySet.as_manager()

    class Meta:
        verbose_name = "sanción"
        verbose_name_plural = "sanciones"
        ordering = ["-inicio"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(tipo="temporal", fin__isnull=False)
                    | models.Q(tipo="permanente", fin__isnull=True)
                ),
                name="sancion_fin_segun_tipo",
                violation_error_message="La temporal necesita fecha de fin; la permanente no.",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} de {self.usuario or 'cuenta eliminada'}"


class Domicilio(models.Model):
    """Dónde vive una persona (CU-03).

    El punto exacto es privado: no se muestra ni se entrega a otras pantallas. Todo lo
    que se publica usa "ubicacion_desplazada", un punto al azar a menos de
    RADIO_DOMICILIO_METROS del exacto. Se calcula una sola vez al guardar: si cambiara en
    cada consulta, mirándolo muchas veces se podría deducir el exacto (RNF3).
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="domicilio"
    )
    # Guarda domicilio con punto
    ubicacion = PointField(srid=4326)
    ubicacion_desplazada = PointField(srid=4326)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "domicilio"
        verbose_name_plural = "domicilios"

    def __str__(self):
        return f"Domicilio de {self.usuario}"
