from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.fichas.models import FichaAnimal

# Tope provisorio del cupo que un hogar puede declarar.
MAX_CUPO_DECLARADO = 20


class PerfilTransito(models.Model):
    """Perfil de hogar de tránsito.

    El rol de hogar de tránsito no se guarda en "Usuario.rol": se deriva de tener un perfil
    activo (ver servicios.es_hogar_de_transito). Las especies y los tamaños son los de la
    ficha de animal, para poder compararlos.
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="perfil_transito",
    )
    # Valores de FichaAnimal.Especie separados por coma, por ejemplo "perro,gato".
    especies_aceptadas = models.CharField("especies que acepta", max_length=60)
    tamano_maximo = models.CharField(
        "tamaño máximo", max_length=20, choices=FichaAnimal.Tamano.choices
    )
    duracion_maxima_dias = models.PositiveSmallIntegerField("duración máxima (días)")
    acepta_medicacion = models.BooleanField("acepta animales con medicación", default=False)
    acepta_conducta = models.BooleanField(
        "acepta animales con problemas de conducta", default=False
    )
    # True: disponible. False: en pausa hasta "pausa_hasta".
    disponibilidad = models.BooleanField("disponible", default=True)
    pausa_hasta = models.DateField("en pausa hasta", null=True, blank=True)
    cupo_declarado = models.PositiveSmallIntegerField(
        "cupo declarado",
        validators=[MinValueValidator(1), MaxValueValidator(MAX_CUPO_DECLARADO)],
    )
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "perfil de tránsito"
        verbose_name_plural = "perfiles de tránsito"

    def __str__(self):
        return f"Perfil de tránsito de {self.usuario}"

    @property
    def especies(self):
        """Las especies que acepta, como lista."""
        return [especie for especie in self.especies_aceptadas.split(",") if especie]
