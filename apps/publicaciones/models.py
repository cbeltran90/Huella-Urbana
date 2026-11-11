from django.conf import settings
from django.contrib.gis.db import models
from django.utils import timezone

from apps.fichas.models import FichaAnimal


class Publicacion(models.Model):
    """Hecho localizado en el tiempo y en el espacio."""

    class Tipo(models.TextChoices):
        EXTRAVIO = "extravio", "Extravío"
        HALLAZGO = "hallazgo", "Hallazgo"
        ADOPCION = "adopcion", "Adopción"
        TRANSITO = "transito", "Tránsito"
        PELIGROSO = "peligroso", "Avistamiento de animal peligroso"
        SILVESTRE = "silvestre", "Avistamiento de fauna silvestre"

    class Estado(models.TextChoices):
        VIGENTE = "vigente", "Vigente"
        RESUELTA = "resuelta", "Resuelta"
        ELIMINADA = "eliminada", "Eliminada"  # borrado lógico por moderación

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,  # la cuenta puede eliminarse
        related_name="publicaciones",
    )
    ficha = models.ForeignKey(
        "fichas.FichaAnimal",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,  # una publicación puede quedar suelta
        related_name="publicaciones",
    )
    # Siempre el punto que se puede mostrar (el desplazado, si viene de un domicilio).
    ubicacion = models.PointField(srid=4326)
    descripcion = models.TextField(blank=True)
    fecha = models.DateTimeField(default=timezone.now)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.VIGENTE)
    fecha_eliminacion = models.DateTimeField(null=True, blank=True)
    etiqueta_urgente = models.BooleanField(default=False)
    telefono_visible = models.CharField(max_length=30, blank=True)
    # Solo si el cuidador no tiene cuenta (lo carga un moderador).
    ubicacion_desplazada = models.PointField(srid=4326, null=True, blank=True)
    especie = models.CharField(max_length=20, blank=True)
    tamano = models.CharField(
        "tamaño", max_length=20, choices=FichaAnimal.Tamano.choices, blank=True
    )
    raza = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=100, blank=True)
    estado_aparente = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "publicación"
        verbose_name_plural = "publicaciones"
        ordering = ["-fecha"]
        indexes = [models.Index(fields=["autor", "fecha"], name="publicacion_autor_fecha")]

    def __str__(self):
        return f"{self.get_tipo_display()} #{self.pk}"
