from django.conf import settings
from django.db import models
from django.utils import timezone


class Adopcion(models.Model):
    "Entrega definitiva de un animal a un adoptante"

    ficha = models.ForeignKey(
        "fichas.FichaAnimal",
        on_delete=models.PROTECT,  # una adopción no se pierde al tocar la ficha
        related_name="adopciones",
    )
    adoptante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="adopciones",
    )
    entregado_por = models.ForeignKey(  # nulo si quien lo encontró se quedó con el animal
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="entregas",
    )
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "adopción"
        verbose_name_plural = "adopciones"

    def __str__(self):
        return f"Adopción de {self.ficha} ({self.fecha:%d/%m/%Y})"
