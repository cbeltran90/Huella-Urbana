from django.conf import settings
from django.db import models


class FichaAnimal(models.Model):
    "Ficha única de un animal de compañía"

    class Estado(models.TextChoices):
        REGISTRADO = "registrado", "Registrado"
        SIN_RESPONSABLE = "sin_responsable", " Sin responsable"
        EN_ADOPCION = "en_adopcion", "En adopción"
        EN_TRANSITO = "en_transito", "En tránsito"

    class Especie(models.TextChoices):
        PERRO = "perro", "Perro"
        GATO = "gato", "Gato"

    class Tamano(models.TextChoices):  # ordenados: sirve para comparar con tamano_maximo
        PEQUENO = "pequeno", "Pequeño"
        MEDIANO = "mediano", "Mediano"
        GRANDE = "grande", "Grande"

    nombre = models.CharField(max_length=100, blank=True)  # opcional
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.REGISTRADO)
    especie = models.CharField(max_length=20, choices=Especie.choices)
    tamano = models.CharField("tamaño", max_length=20, choices=Tamano.choices, blank=True)
    edad_estimada = models.CharField(max_length=40, blank=True)
    color = models.CharField(max_length=60, blank=True)
    raza = models.CharField(max_length=80, blank=True)
    castrado = models.BooleanField(default=False)
    desparasitado = models.BooleanField(default=False)
    vacunado = models.BooleanField(default=False)
    chip = models.CharField(max_length=40, blank=True)
    temperamento = models.CharField(max_length=120, blank=True)
    requiere_medicacion = models.BooleanField(default=False)  # se cruza con acepta_medicacion
    problemas_conducta = models.BooleanField(default=False)  # se cruza con acepta_conducta
    compatible_ninos = models.BooleanField(default=False)
    compatible_animales = models.BooleanField(default=False)
    es_privada = models.BooleanField(default=True)  # alta preventiva

    responsable = models.ForeignKey(  # nulo si no tiene o no es usuario
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fichas_responsable",
    )
    cuidador = models.ForeignKey(  # quien lo tiene a su cargo, nulo si está  en un hogar
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fichas_a_cargo",
    )
    cuidador_contacto = models.CharField(max_length=100, blank=True)  # si no es usuario

    # Incio del plazo de ausencia: solo corre si hay cuidador.
    sin_responsable_desde = models.DateField(null=True, blank=True)

    # Contacto del responsable cuando no es usuario.
    contacto_externo = models.CharField(max_length=120, blank=True)

    fusionada_en = models.ForeignKey(  # ficha principal en la que se fusionó
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="fusionadas",
    )

    class Meta:
        ordering = ["-id"]
        verbose_name = "ficha"
        verbose_name_plural = "fichas"

    def __str__(self):
        return self.nombre or f"Ficha #{self.pk}"
