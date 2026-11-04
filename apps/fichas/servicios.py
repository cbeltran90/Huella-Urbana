import logging

from django.db import transaction
from django.utils import timezone

from .models import FichaAnimal
from .transiciones import TransicionInvalida, transicion_permitida

logger = logging.getLogger(__name__)

# Campos que un cambio de estado puede modificar a la vez.
CAMPOS_MODIFICABLES = frozenset(
    {
        "responsable",
        "cuidador",
        "cuidador_contacto",
        "sin_responsable_desde",
        "contacto_externo",
        "es_privada",
    }
)


@transaction.atomic
def cambiar_estado(ficha, nuevo_estado, *, actor, cambios=None):
    """Pasa la ficha a 'nuevo_estado' si la transición está permitida.

    'actor' es el usuario que lo provoca, o 'None' si lo hace el sistema.
    'cambios' es un diccionario opcional de campos de 'CAMPOS_MODIFICABLES'
    que se guardan junto con el estado, en la misma transacción.

    Lanza 'TransicionInvalida' si el cambio no está permitido y 'ValueError' si 'cambios' incluye
    un campo no modificable. Este es el único camino para cambiar el estado: no se asigna
    'ficha.estado' manualmente.
    """
    cambios = cambios or {}
    no_permitidos = set(cambios) - CAMPOS_MODIFICABLES
    if no_permitidos:
        raise ValueError(
            f"Campos que no se pueden cambiar junto con el estado: {sorted(no_permitidos)}"
        )

    # Se relee el estado desde la base y se bloquea la fila, para no pisar un cambio simultáneo.
    origen = FichaAnimal.objects.select_for_update().only("estado").get(pk=ficha.pk).estado
    if not transicion_permitida(origen, nuevo_estado):
        raise TransicionInvalida(f"No se puede pasar una ficha de {origen} a {nuevo_estado}.")

    ficha.estado = nuevo_estado
    for campo, valor in cambios.items():
        setattr(ficha, campo, valor)
    ficha.save(update_fields=["estado", *cambios])

    logger.info(
        "Ficha %s: %s -> %s (%s)",
        ficha.pk,
        origen,
        nuevo_estado,
        actor if actor is not None else "sistema",
    )
    return ficha


# Campos que el usuario carga y edita en la ficha.
CAMPOS_EDITABLES = (
    "nombre",
    "especie",
    "tamano",
    "edad_estimada",
    "color",
    "raza",
    "castrado",
    "desparasitado",
    "vacunado",
    "chip",
    "temperamento",
    "requiere_medicacion",
    "problemas_conducta",
    "compatible_ninos",
    "compatible_animales",
)


def crear_ficha(usuario, datos):
    """Alta preventiva: ficha registrada, privada y con el usuario como responsable."""
    datos = {campo: datos[campo] for campo in CAMPOS_EDITABLES if campo in datos}
    return FichaAnimal.objects.create(
        responsable=usuario,
        estado=FichaAnimal.Estado.REGISTRADO,
        es_privada=True,
        **datos,
    )


def editar_ficha(ficha, datos):
    """Edición: solo se tocan los campos de CAMPOS_EDITABLES."""
    campos = [campo for campo in CAMPOS_EDITABLES if campo in datos]
    for campo in campos:
        setattr(ficha, campo, datos[campo])
    ficha.save(update_fields=campos)
    return ficha


def dar_de_baja(ficha):
    """Borra la ficha. Quien llama ya comprobó "permisos.puede_dar_de_baja"."""
    ficha.delete()


def crear_ficha_sin_responsable(datos, *, cuidador=None):
    """Hallazgo: ficha nueva en "sin responsable", privada.

    Si alguien tiene al animal consigo, queda a su cargo y empieza a correr el plazo de
    ausencia. Si no, nadie lo tiene a cargo y el plazo no corre.
    """
    datos = {campo: datos[campo] for campo in CAMPOS_EDITABLES if campo in datos}
    return FichaAnimal.objects.create(
        estado=FichaAnimal.Estado.SIN_RESPONSABLE,
        responsable=None,
        cuidador=cuidador,
        sin_responsable_desde=timezone.localdate() if cuidador else None,
        es_privada=True,
        **datos,
    )


def crear_ficha_en_adopcion(datos, *, cuidador):
    """Alta directa en adopción: ficha nueva en "en adopción", a cargo de quien la da de alta.

    No tiene responsable (titular) y es pública, porque está en el circuito y quienes se
    postulan necesitan ver sus datos.
    """
    datos = {campo: datos[campo] for campo in CAMPOS_EDITABLES if campo in datos}
    return FichaAnimal.objects.create(
        estado=FichaAnimal.Estado.EN_ADOPCION,
        responsable=None,
        cuidador=cuidador,
        es_privada=False,
        **datos,
    )
