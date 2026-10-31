import hashlib

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class UsuarioManager(UserManager):
    """Manager personalizado para crear usuarios con email en lugar de username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("El email es obligatorio")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class Usuario(AbstractUser):
    """Usuario del sistema. Se extiende acá para no migrar el modelo más adelante."""

    username = None
    email = models.EmailField("correo electrónico", unique=True)

    email_hash = models.CharField(max_length=64, blank=True)
    nombre_usuario = models.CharField("nombre de usuario", max_length=150, unique=True)
    rol = models.CharField(max_length=20, default="registrado")
    es_organizacion = models.BooleanField(default=False)
    es_zoonosis = models.BooleanField(default=False)
    estado_cuenta = models.CharField(max_length=20, default="pendiente")
    fecha_registro = models.DateTimeField(auto_now_add=True)
    acepto_condiciones_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nombre_usuario"]

    objects = UsuarioManager()  # <--- ESTA LÍNEA ES LA CLAVE

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
            self.email_hash = hashlib.sha256(self.email.encode("utf-8")).hexdigest()

        self.is_active = self.estado_cuenta == "activa"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre_usuario
