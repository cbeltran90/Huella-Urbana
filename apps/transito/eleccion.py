"""Elegir hogar de tránsito entre quienes se postularon."""

import logging
from dataclasses import dataclass

from django.db import transaction

from apps.fichas.models import FichaAnimal
from apps.fichas.permisos import es_cuidador, es_moderador, es_responsable
from apps.notificaciones.models import Notificacion
from apps.notificaciones.servicios import notificar

from .models import Alojamiento, PerfilTransito, Postulacion
from .servicios import cupo_libre, hogar_habilitado, incompatibilidades

logger = logging.getLogger(__name__)

MENSAJE_NO_PUEDE_ELEGIR = "No podés elegir hogar de tránsito para esta mascota."
MENSAJE_POSTULACION_NO_DISPONIBLE = "Esa postulación ya no está disponible."
MENSAJE_HOGAR_NO_HABILITADO = "Ese hogar ya no está habilitado. Elegí a otro."
MENSAJE_YA_HAY_ELEGIDO = "Ya hay un hogar elegido para esta mascota."


class EleccionNoPermitida(Exception):
    """Quien elige no puede, o la ficha ya no está en adopción."""


class PostulacionNoDisponible(Exception):
    """La postulación no es de tránsito para esta ficha o ya no está pendiente."""


class HogarNoHabilitado(Exception):
    """El hogar elegido ya no está habilitado (extensión 4A): no se elige y no cambia nada."""


class HogarYaElegido(Exception):
    """Ya hay una postulación de tránsito elegida para esta ficha."""


@dataclass(frozen=True)
class Postulante:
    """Un postulante habilitado, con lo que ve quien elige."""

    postulacion: Postulacion
    perfil: PerfilTransito
    advertencias: list  # por qué el hogar no encaja con el animal (vacía si encaja)
    cupo_libre: int

    @property
    def contacto(self):
        return self.postulacion.contacto


def _aloja_hoy(usuario, ficha):
    return Alojamiento.objects.filter(
        ficha=ficha, hogar_id=usuario.pk, fecha_fin_real__isnull=True
    ).exists()


def puede_elegir(usuario, ficha):
    """Quien tiene el animal a su cargo, su responsable, el hogar que lo aloja (relevo) o un
    moderador, con la ficha en "en adopción".
    """
    if not usuario.is_authenticated or ficha.estado != FichaAnimal.Estado.EN_ADOPCION:
        return False
    return (
        es_cuidador(usuario, ficha)
        or es_responsable(usuario, ficha)
        or es_moderador(usuario)
        or _aloja_hoy(usuario, ficha)
    )


def _postulaciones_de_transito(ficha):
    return Postulacion.objects.filter(ficha=ficha, tipo=Postulacion.Tipo.TRANSITO)


def hay_hogar_elegido(ficha):
    return _postulaciones_de_transito(ficha).filter(estado=Postulacion.Estado.ELEGIDA).exists()


def postulantes_habilitados(ficha, hoy=None):
    """Los hogares con postulación de tránsito pendiente que hoy están habilitados.

    Habilitado: perfil activo y disponible, cuenta activa y sin sanción vigente. Van del más
    antiguo al más nuevo. Las postulaciones de adopción no cuentan. Una postulación pendiente
    de alguien que dejó de estar habilitado no aparece, pero sigue pendiente.
    """
    pendientes = list(
        _postulaciones_de_transito(ficha)
        .filter(estado=Postulacion.Estado.PENDIENTE)
        .select_related("usuario")
    )
    perfiles = PerfilTransito.objects.filter(
        usuario__in=[p.usuario_id for p in pendientes], activo=True
    ).select_related("usuario")
    por_usuario = {perfil.usuario_id: perfil for perfil in perfiles}
    resultado = []
    for postulacion in pendientes:
        perfil = por_usuario.get(postulacion.usuario_id)
        if perfil is None or not hogar_habilitado(perfil, hoy):
            continue
        resultado.append(
            Postulante(
                postulacion=postulacion,
                perfil=perfil,
                advertencias=incompatibilidades(perfil, ficha),
                cupo_libre=cupo_libre(perfil),
            )
        )
    return resultado


def elegir_hogar(ficha, actor, postulacion, hoy=None):
    """Elige el hogar de tránsito: su postulación queda elegida y las demás, descartadas.

    Se revalida todo con lo que hay en la base: que la ficha siga en adopción, que 'actor'
    pueda elegir, que no haya otro hogar elegido, que la postulación siga pendiente y que el
    hogar siga habilitado (en ese caso no se elige y no cambia nada). El cupo no
    es condición. Solo se tocan las postulaciones de tránsito: las de adopción siguen como
    estaban, y la ficha sigue en "en adopción" (pasa a tránsito al registrar la entrega).
    Después de guardar, avisa al elegido y a los descartados; si un aviso falla, la elección
    queda. Devuelve la postulación elegida.
    """
    elegida, descartadas = _marcar_elegida(ficha, actor, postulacion, hoy)
    _avisar_del_resultado(ficha, elegida, descartadas)
    return elegida


@transaction.atomic
def _marcar_elegida(ficha, actor, postulacion, hoy):
    FichaAnimal.objects.select_for_update().get(pk=ficha.pk)
    ficha.refresh_from_db(fields=["estado", "cuidador", "responsable"])
    if not puede_elegir(actor, ficha):
        raise EleccionNoPermitida(MENSAJE_NO_PUEDE_ELEGIR)
    if hay_hogar_elegido(ficha):
        raise HogarYaElegido(MENSAJE_YA_HAY_ELEGIDO)

    actual = (
        _postulaciones_de_transito(ficha)
        .select_for_update()
        .select_related("usuario")
        .filter(pk=postulacion.pk)
        .first()
    )
    if actual is None or actual.estado != Postulacion.Estado.PENDIENTE:
        raise PostulacionNoDisponible(MENSAJE_POSTULACION_NO_DISPONIBLE)

    perfil = PerfilTransito.objects.filter(usuario_id=actual.usuario_id, activo=True).first()
    if perfil is None or not hogar_habilitado(perfil, hoy):
        raise HogarNoHabilitado(MENSAJE_HOGAR_NO_HABILITADO)

    descartadas = list(
        _postulaciones_de_transito(ficha)
        .select_for_update()
        .select_related("usuario")
        .filter(estado=Postulacion.Estado.PENDIENTE)
        .exclude(pk=actual.pk)
    )
    actual.estado = Postulacion.Estado.ELEGIDA
    actual.save(update_fields=["estado"])
    Postulacion.objects.filter(pk__in=[p.pk for p in descartadas]).update(
        estado=Postulacion.Estado.DESCARTADA
    )
    postulacion.estado = actual.estado
    return actual, descartadas


def _avisar_del_resultado(ficha, elegida, descartadas):
    nombre = ficha.nombre or "la mascota"
    avisos = [
        (
            elegida,
            f"¡Te eligieron como hogar de tránsito de {nombre}!",
            "Quien la tiene a su cargo se va a comunicar con vos por el contacto que dejaste.",
        )
    ]
    avisos += [
        (
            postulacion,
            f"Tu postulación de tránsito para {nombre} no fue elegida",
            "Se eligió a otro hogar. Gracias por ofrecerte: podés postularte a otras mascotas.",
        )
        for postulacion in descartadas
    ]
    for postulacion, titulo, mensaje in avisos:
        try:
            notificar(
                postulacion.usuario,
                Notificacion.Tipo.RESULTADO_POSTULACION,
                titulo,
                mensaje,
                ficha=ficha,
            )
        except Exception:
            logger.exception("No se pudo avisar el resultado de la postulación %s", postulacion.pk)
