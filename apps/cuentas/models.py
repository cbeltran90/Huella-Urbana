from django.contrib.auth.models import AbstractUser


class Usuario(AbstractUser):
    """Usuario del sistema. Se extiende acá para no migrar el modelo más adelante."""
