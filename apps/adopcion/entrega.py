"""Concretar la adopción de quien se eligió, o cancelarla (CU-30)."""

from django.db import transaction
from django.utils import timezone

from apps.fichas.models import FichaAnimal
from apps.fichas.permisos import es_moderador
from apps.fichas.servicios import cambiar_estado
from apps.notificaciones.models import Notificacion
from apps.notificaciones.servicios import notificar
from apps.transito.models import Alojamiento, Postulacion
from apps.transito.postulaciones import ESTADOS_ACTIVOS
from apps.transito.servicios import marcar_concretada

from .eleccion import MENSAJE_A_LOS_DEMAS, elegida_de, puede_elegir
from .models import Adopcion
from .postulaciones import ESTADOS_DISPONIBLES

MENSAJE_NO_PUEDE = "Solo quien entrega la mascota o un moderador puede hacer esto."
MENSAJE_SIN_ELEGIDO = "Todavía no se eligió quién la adopta."
MENSAJE_AL_ADOPTANTE = "Gracias por darle un hogar."
MENSAJE_CANCELADA = "Si seguís con ganas, podés volver a postularte desde la ficha."


class EntregaNoPermitida(ValueError):
    """No se puede concretar ni cancelar la adopción; el mensaje se puede mostrar."""


def puede_entregar(usuario, ficha):
    """Quien eligió al adoptante, o cualquier moderador (CU-30)."""
    return puede_elegir(usuario, ficha) or es_moderador(usuario)


def _validar(ficha, actor):
    """Bloquea y relee la ficha; devuelve la ficha y la postulación elegida."""
    ficha = FichaAnimal.objects.select_for_update().get(pk=ficha.pk)
    if not puede_entregar(actor, ficha):
        raise EntregaNoPermitida(MENSAJE_NO_PUEDE)
    elegida = elegida_de(ficha)
    if ficha.estado not in ESTADOS_DISPONIBLES or elegida is None:
        raise EntregaNoPermitida(MENSAJE_SIN_ELEGIDO)
    return ficha, elegida


def concretar_adopcion(ficha, actor):
    """La mascota ya está con quien la adopta: se registra la adopción y se devuelve.

    La ficha pasa a "registrado" con el adoptante como responsable (su publicación de
    adopción queda resuelta), se cierra el alojamiento si estaba en un hogar de tránsito y
    se descartan las postulaciones que quedaban, con aviso. Los puntos del tránsito quedan
    fuera de esta entrega. Lanza EntregaNoPermitida si el actor no puede o no hay nadie
    elegido; en ese caso no cambia nada.
    """
    with transaction.atomic():
        actual, elegida = _validar(ficha, actor)
        adoptante = elegida.usuario
        entrega = actual.cuidador or actual.responsable
        marcar_concretada(elegida)
        adopcion = Adopcion.objects.create(
            ficha=actual,
            adoptante=adoptante,
            # Nadie la entrega si quien la tenía a cargo se la queda.
            entregado_por=None if entrega == adoptante else entrega,
        )
        Alojamiento.objects.filter(ficha=actual, fecha_fin_real__isnull=True).update(
            fecha_fin_real=timezone.localdate(), motivo_fin=Alojamiento.MotivoFin.ADOPCION
        )
        descartadas = list(
            actual.postulaciones.filter(estado__in=ESTADOS_ACTIVOS).select_related("usuario")
        )
        Postulacion.objects.filter(pk__in=[p.pk for p in descartadas]).update(
            estado=Postulacion.Estado.DESCARTADA
        )
        cambiar_estado(
            actual, FichaAnimal.Estado.REGISTRADO, actor=actor, cambios={"responsable": adoptante}
        )
        _avisar_adopcion(actual, adoptante, descartadas)
    ficha.refresh_from_db()
    return adopcion


def _avisar_adopcion(ficha, adoptante, descartadas):
    nombre = ficha.nombre or "La mascota"
    notificar(
        adoptante,
        Notificacion.Tipo.RESULTADO_POSTULACION,
        f"¡{nombre} ya es parte de tu familia!",
        MENSAJE_AL_ADOPTANTE,
        ficha=ficha,
    )
    for postulacion in descartadas:
        notificar(
            postulacion.usuario,
            Notificacion.Tipo.RESULTADO_POSTULACION,
            f"{nombre} ya encontró un hogar",
            MENSAJE_A_LOS_DEMAS,
            ficha=ficha,
        )


def cancelar_eleccion(ficha, actor):
    """La adopción no se concretó (1A): la ficha sigue igual y la elegida queda descartada.

    Se avisa a esa persona, que puede volver a postularse. Las que se descartaron al elegir
    no vuelven solas. Lanza EntregaNoPermitida si el actor no puede o no hay nadie elegido.
    """
    with transaction.atomic():
        actual, elegida = _validar(ficha, actor)
        elegida.estado = Postulacion.Estado.DESCARTADA
        elegida.save(update_fields=["estado"])
        notificar(
            elegida.usuario,
            Notificacion.Tipo.RESULTADO_POSTULACION,
            f"La adopción de {actual.nombre or 'la mascota'} no se concretó",
            MENSAJE_CANCELADA,
            ficha=actual,
        )
    return elegida
