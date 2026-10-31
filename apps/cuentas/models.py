import hashlib
from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """Usuario del sistema. Se extiende acá para no migrar el modelo más adelante."""
    
    # Quitamos el username por defecto y usamos el email como credencial principal
    username = None
    email = models.EmailField("correo electrónico", unique=True)
    
    # Campos del DER
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

    def save(self, *args, **kwargs):
        # 1. Normalizar el correo (minúsculas y sin espacios)
        if self.email:
            self.email = self.email.strip().lower()
            # 2. Generar el hash SHA-256
            self.email_hash = hashlib.sha256(self.email.encode("utf-8")).hexdigest()
        
        # 3. Sincronizar is_active con estado_cuenta (RF1.1 y CU-02)
        self.is_active = self.estado_cuenta == "activa"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre_usuario