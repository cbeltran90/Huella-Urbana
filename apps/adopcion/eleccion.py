"""Elegir adoptante entre quienes se postularon para adoptar (CU-29)."""

from django.db import transaction

from apps.fichas.models import FichaAnimal
from apps.fichas.permisos import es_moderador
from apps.notificaciones.models import Notificacion
from apps.notificaciones.servicios import notificar
from apps.transito.models import Postulacion

from .postulaciones import ESTADOS_DISPONIBLES, advertencias_de_postulacion

MENSAJE_NO_PUEDE_ELEGIR = "Solo quien tiene la mascota a su cargo puede elegir a quién darla."
MENSAJE_NO_DISPONIBLE = "Esta mascota ya no busca familia."
MENSAJE_NO_PENDIENTE = "Esa postulación ya no está pendiente."
MENSAJE_YA_HAY_ELEGIDO = "Ya elegiste a quién darla en adopción."
MENSAJE_AL_ELEGIDO = "Pronto se van a comunicar con vos para coordinar la entrega."
MENSAJE_A_LOS_DEMAS = "Gracias por tu interés. Hay otras mascotas que te están esperando."
DUDA_NINOS = "En el hogar viven niños y no sabemos si esta mascota se lleva bien con ellos."
DUDA_ANIMALES = "El hogar ya tiene mascotas y no sabemos si esta se lleva bien con otros animales."


class EleccionNoPermitida(ValueError):
    """No se puede elegir esa postulación; el mensaje se puede mostrar."""


def puede_elegir(usuario, ficha):
    """True si la persona elige adoptante para este animal.

    Elige el cuidador; si no hay, el responsable (quien da su animal en adopción); si no hay
    ningún usuario a cargo, un moderador.
    """
    if not usuario.is_authenticated:
        return False
    a_cargo = ficha.cuidador_id or ficha.responsable_id
    if a_cargo is not None:
        return usuario.pk == a_cargo
    return es_moderador(usuario)


def postulantes_de(ficha):
    """Las postulaciones para adoptar que esperan una respuesta, de la más vieja a la más nueva."""
    return ficha.postulaciones.filter(
        tipo=Postulacion.Tipo.ADOPCION, estado=Postulacion.Estado.PENDIENTE
    ).select_related("usuario")


def elegida_de(ficha):
    """La postulación para adoptar que ya se eligió, o None."""
    return (
        ficha.postulaciones.filter(
            tipo=Postulacion.Tipo.ADOPCION, estado=Postulacion.Estado.ELEGIDA
        )
        .select_related("usuario")
        .first()
    )


def dudas_de(postulacion):
    """Por qué el hogar de quien se postuló podría no ser compatible, contado a quien elige."""
    return advertencias_de_postulacion(
        postulacion.usuario, postulacion.ficha, (DUDA_NINOS, DUDA_ANIMALES)
    )


def elegir_adoptante(postulacion, actor):
    """Elige esa postulación: queda elegida, las demás de adopción descartadas, y se avisa a todos.

    Las de tránsito no se tocan (se resuelven al concretar la adopción, C8). Lanza
    EleccionNoPermitida si el actor no elige para ese animal, si el animal ya no está
    disponible, si la postulación no es de adopción o no está pendiente, o si ya hay un
    elegido. En esos casos no cambia nada.
    """
    with transaction.atomic():
        # Bloquear la ficha evita que dos elecciones a la vez terminen con dos elegidos.
        ficha = FichaAnimal.objects.select_for_update().get(pk=postulacion.ficha_id)
        elegida = Postulacion.objects.get(pk=postulacion.pk)
        if elegida.tipo != Postulacion.Tipo.ADOPCION or not puede_elegir(actor, ficha):
            raise EleccionNoPermitida(MENSAJE_NO_PUEDE_ELEGIR)
        if ficha.estado not in ESTADOS_DISPONIBLES:
            raise EleccionNoPermitida(MENSAJE_NO_DISPONIBLE)
        if elegida.estado != Postulacion.Estado.PENDIENTE:
            raise EleccionNoPermitida(MENSAJE_NO_PENDIENTE)
        if elegida_de(ficha) is not None:
            raise EleccionNoPermitida(MENSAJE_YA_HAY_ELEGIDO)
        descartadas = list(postulantes_de(ficha).exclude(pk=elegida.pk))
        elegida.estado = Postulacion.Estado.ELEGIDA
        elegida.save(update_fields=["estado"])
        Postulacion.objects.filter(pk__in=[p.pk for p in descartadas]).update(
            estado=Postulacion.Estado.DESCARTADA
        )
        _avisar(ficha, elegida, descartadas)
    postulacion.estado = elegida.estado
    return postulacion


def _avisar(ficha, elegida, descartadas):
    nombre = ficha.nombre or "la mascota"
    notificar(
        elegida.usuario,
        Notificacion.Tipo.RESULTADO_POSTULACION,
        f"¡Te eligieron para adoptar a {nombre}!",
        MENSAJE_AL_ELEGIDO,
        ficha=ficha,
    )
    for postulacion in descartadas:
        notificar(
            postulacion.usuario,
            Notificacion.Tipo.RESULTADO_POSTULACION,
            f"{ficha.nombre or 'La mascota'} ya encontró un hogar",
            MENSAJE_A_LOS_DEMAS,
            ficha=ficha,
        )
