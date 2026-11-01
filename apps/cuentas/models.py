import hashlib

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


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
        campos = kwargs.get("update_fields")
        if campos is not None and "estado_cuenta" in campos:
            kwargs["update_fields"] = {*campos, "is_active"}
        super().save(*args, **kwargs)
