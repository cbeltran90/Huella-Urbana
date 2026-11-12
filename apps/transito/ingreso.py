"""Ingreso de la mascota al hogar de tránsito elegido, o la cancelación de la entrega (CU-26)."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.fichas.models import FichaAnimal
from apps.fichas.servicios import cambiar_estado
from apps.notificaciones.models import Notificacion
from apps.notificaciones.servicios import notificar
from apps.publicaciones import servicios as publicaciones

from . import eleccion
from .models import Alojamiento, PerfilTransito, Postulacion
from .servicios import cupo_libre, hogar_habilitado, marcar_concretada

MENSAJE_NO_PUEDE = (
    "Solo quien entrega la mascota, el hogar elegido o un moderador puede hacer esto."
)
MENSAJE_SIN_HOGAR = "Todavía no se eligió un hogar de tránsito."
MENSAJE_HOGAR_NO_HABILITADO = (
    "Ese hogar ya no está disponible. Podés cancelar la entrega y elegir otro."
)
MENSAJE_SIN_LUGAR = "Ese hogar ya no tiene lugar libre. Podés cancelar la entrega y elegir otro."
MENSAJE_AL_HOGAR = "Se queda con vos hasta el {fin:%d/%m}. ¡Gracias por darle un lugar!"
MENSAJE_A_QUIEN_ENTREGA = "¡Gracias por todo lo que hiciste!"


class IngresoNoPermitido(ValueError):
    """No se puede registrar el ingreso ni cancelar la entrega; el mensaje se puede mostrar."""


def hogar_elegido(ficha):
    """La postulación de tránsito elegida de la ficha, o None."""
    return (
        ficha.postulaciones.filter(
            tipo=Postulacion.Tipo.TRANSITO, estado=Postulacion.Estado.ELEGIDA
        )
        .select_related("usuario")
        .first()
    )


def puede_registrar_ingreso(usuario, ficha):
    """Quien puede elegir el hogar o el propio hogar elegido, con la ficha en adopción."""
    if not usuario.is_authenticated or ficha.estado != FichaAnimal.Estado.EN_ADOPCION:
        return False
    if eleccion.puede_elegir(usuario, ficha):
        return True
    elegida = hogar_elegido(ficha)
    return elegida is not None and elegida.usuario_id == usuario.pk


def _validar(ficha, actor):
    """Bloquea y relee la ficha; devuelve la ficha y la postulación del hogar elegido."""
    actual = FichaAnimal.objects.select_for_update().get(pk=ficha.pk)
    if not puede_registrar_ingreso(actor, actual):
        raise IngresoNoPermitido(MENSAJE_NO_PUEDE)
    elegida = hogar_elegido(actual)
    if elegida is None:
        raise IngresoNoPermitido(MENSAJE_SIN_HOGAR)
    return actual, elegida


def registrar_ingreso(ficha, actor, *, vacunado=False, castrado=False, desparasitado=False):
    """La mascota llegó al hogar elegido: se registra el alojamiento y se devuelve.

    Revalida que el hogar siga habilitado y tenga lugar libre. La ficha pasa a "en tránsito"
    con el hogar a cargo (la publicación de adopción queda resuelta) y se publica en
    tránsito. El alojamiento termina, como mucho, a los días de duración máxima del hogar.
    Lanza IngresoNoPermitido si no se puede; en ese caso no cambia nada.
    """
    with transaction.atomic():
        actual, elegida = _validar(ficha, actor)
        perfil = PerfilTransito.objects.filter(usuario_id=elegida.usuario_id, activo=True).first()
        if perfil is None or not hogar_habilitado(perfil):
            raise IngresoNoPermitido(MENSAJE_HOGAR_NO_HABILITADO)
        if cupo_libre(perfil) < 1:
            raise IngresoNoPermitido(MENSAJE_SIN_LUGAR)
        entrega = actual.cuidador or actual.responsable
        hoy = timezone.localdate()
        alojamiento = Alojamiento.objects.create(
            ficha=actual,
            hogar=perfil,
            fecha_ingreso=hoy,
            fecha_fin_prevista=hoy + timedelta(days=perfil.duracion_maxima_dias),
            vacunado_al_ingreso=vacunado,
            castrado_al_ingreso=castrado,
            desparasitado_al_ingreso=desparasitado,
        )
        marcar_concretada(elegida)
        cambiar_estado(
            actual,
            FichaAnimal.Estado.EN_TRANSITO,
            actor=actor,
            cambios={"cuidador": elegida.usuario, "cuidador_contacto": ""},
        )
        publicaciones.publicar_transito_de_ficha(actual, actor)
        _avisar_ingreso(actual, alojamiento, elegida.usuario, entrega)
    ficha.refresh_from_db()
    return alojamiento


def _avisar_ingreso(ficha, alojamiento, hogar, entrega):
    nombre = ficha.nombre or "La mascota"
    notificar(
        hogar,
        Notificacion.Tipo.NOVEDAD,
        f"¡{nombre} ya está en tu hogar!",
        MENSAJE_AL_HOGAR.format(fin=alojamiento.fecha_fin_prevista),
        ficha=ficha,
    )
    if entrega is not None and entrega != hogar:
        notificar(
            entrega,
            Notificacion.Tipo.NOVEDAD,
            f"{nombre} ya está en su hogar de tránsito",
            MENSAJE_A_QUIEN_ENTREGA,
            ficha=ficha,
        )
