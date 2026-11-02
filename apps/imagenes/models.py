from django.conf import settings
from django.core.files.storage import default_storage
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


class Fotografia(models.Model):
    """Imagen re-codificada sin EXIF, con sus hashes y su marca de revisión."""

    class MotivoRevision(models.TextChoices):
        SIN_ANIMAL = "sin_animal", "Sin animal"
        DUPLICADA = "duplicada", "Duplicada"

    # Solo la ruta dentro de MEDIA_ROOT; el archivo vive en disco, no en la base.
    archivo = models.CharField(max_length=255)
    hash_sha256 = models.CharField(max_length=64, db_index=True)
    hash_perceptual = models.CharField(max_length=16, blank=True, db_index=True)
    embedding = models.BinaryField(null=True, blank=True, editable=False)
    # Nulo = no se pudo verificar.
    tiene_animal = models.BooleanField(null=True, blank=True)
    motivo_revision = models.CharField(max_length=20, choices=MotivoRevision.choices, blank=True)
    revisada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fotografias_revisadas",
    )
    ficha = models.ForeignKey(
        "fichas.FichaAnimal",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="fotografias",
    )

    class Meta:
        verbose_name = "fotografía"
        verbose_name_plural = "fotografías"
        ordering = ["id"]

    def __str__(self):
        return f"Fotografía #{self.pk}"


@receiver(post_delete, sender=Fotografia)
def borrar_archivo(sender, instance, **kwargs):
    """Al borrar la fila (por ejemplo al dar de baja una ficha) se borra el archivo."""
    if instance.archivo:
        default_storage.delete(instance.archivo)
