from django.conf import settings
from django.db import models


class Notificacion(models.Model):
    "Notificación de un evento relevante para un usuario"

    class Tipo(models.TextChoices):
        COINCIDENCIA_TRANSITO = "coincidencia_transito", "Coincidencia de tránsito"
        COINCIDENCIA_BUSQUEDA = "coincidencia_busqueda", "Coincidencia de búsqueda"
        FAVORITO = "favorito", "Favorito"
        VINCULACION = "vinculacion", "Vinculación"
        NOVEDAD = "novedad", "Novedad"
        EVENTO = "evento", "Evento"
        VENCIMIENTO_PLAZO = "vencimiento_plazo", "Vencimiento de plazo"
        RESULTADO_POSTULACION = "resultado_postulacion", "Resultado de postulación"
        POSTULACION_RECIBIDA = "postulacion_recibida", "Postulación recibida"
        ALERTA_SANITARIA = "alerta_sanitaria", "Alerta sanitaria"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificaciones",
    )
    tipo = models.CharField(max_length=25, choices=Tipo.choices)
    titulo = models.CharField(max_length=120)
    mensaje = models.TextField(blank=True)
    ficha = models.ForeignKey(
        "fichas.FichaAnimal",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notificaciones",
    )
    publicacion = models.ForeignKey(
        "publicaciones.Publicacion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notificaciones",
    )
    leida = models.BooleanField(default=False)
    creada_at = models.DateTimeField(auto_now_add=True)
    push_enviado_at = models.DateTimeField(null=True, blank=True, db_index=True)
    reintentos = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-creada_at"]
        verbose_name = "notificación"
        verbose_name_plural = "notificaciones"

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.titulo}"
