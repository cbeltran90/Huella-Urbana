"""Ingreso de la mascota al hogar de tránsito elegido, o la cancelación de la entrega (CU-26)."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.cuentas.servicios import esta_suspendido
from apps.fichas.models import FichaAnimal
from apps.fichas.permisos import es_moderador
from apps.fichas.servicios import cambiar_estado
from apps.notificaciones.models import Notificacion
from apps.notificaciones.servicios import notificar
from apps.publicaciones import servicios as publicaciones

from . import eleccion
from .models import Alojamiento, PerfilTransito, Postulacion
from .servicios import marcar_concretada

MENSAJE_NO_PUEDE = (
    "Solo quien entrega la mascota, el hogar elegido o un moderador puede hacer esto."
)
MENSAJE_SIN_HOGAR = "Todavía no se eligió un hogar de tránsito."
MENSAJE_HOGAR_NO_HABILITADO = (
    "Ese hogar ya no está disponible. Podés cancelar la entrega y elegir otro."
)
MENSAJE_AL_HOGAR = "Se queda con vos hasta el {fin:%d/%m}. ¡Gracias por darle un lugar!"
MENSAJE_A_QUIEN_ENTREGA = "¡Gracias por todo lo que hiciste!"
MENSAJE_CANCELADA_AL_HOGAR = "Si seguís con ganas, podés volver a postularte desde la ficha."
MENSAJE_CANCELADA_A_QUIEN_ENTREGA = "Podés elegir otro hogar desde la ficha."


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
    """Quien puede elegir el hogar, el propio hogar elegido o un moderador, con la ficha en
    adopción. Como al concretar una adopción, el moderador siempre puede.
    """
    if not usuario.is_authenticated or ficha.estado != FichaAnimal.Estado.EN_ADOPCION:
        return False
    if eleccion.puede_elegir(usuario, ficha) or es_moderador(usuario):
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


def alojar_en_hogar(ficha, hogar, *, vacunado=False, castrado=False, desparasitado=False):
    """Registra que la mascota pasa a vivir en el hogar de tránsito de este usuario.

    Revalida que el hogar tenga su perfil activo y no esté suspendido; el cupo puede quedar en
    cero o superarse. Si la mascota venía de otro hogar, ese alojamiento se cierra hoy
    por relevo y libera su plaza. El alojamiento termina, como mucho, a los días de duración
    máxima del hogar. No cambia el estado de la ficha ni su publicación: eso lo hace quien la
    llama. Lanza IngresoNoPermitido si el hogar no está disponible.
    """
    perfil = PerfilTransito.objects.filter(usuario=hogar, activo=True).first()
    if perfil is None or esta_suspendido(hogar):
        raise IngresoNoPermitido(MENSAJE_HOGAR_NO_HABILITADO)
    hoy = timezone.localdate()
    with transaction.atomic():
        Alojamiento.objects.filter(ficha=ficha, fecha_fin_real__isnull=True).update(
            fecha_fin_real=hoy, motivo_fin=Alojamiento.MotivoFin.RELEVO
        )
        return Alojamiento.objects.create(
            ficha=ficha,
            hogar=perfil,
            fecha_ingreso=hoy,
            fecha_fin_prevista=hoy + timedelta(days=perfil.duracion_maxima_dias),
            vacunado_al_ingreso=vacunado,
            castrado_al_ingreso=castrado,
            desparasitado_al_ingreso=desparasitado,
        )


def registrar_ingreso(ficha, actor, *, vacunado=False, castrado=False, desparasitado=False):
    """La mascota llegó al hogar elegido: se registra el alojamiento y se devuelve.

    Revalida que el hogar no esté suspendido; el cupo puede quedar en cero o superarse
    (CU-26). Si venía de otro hogar, ese alojamiento se cierra por relevo. La ficha pasa a
    "en tránsito" con el hogar a cargo (la publicación de adopción queda resuelta) y se
    publica en tránsito. El alojamiento termina, como mucho, a los días de duración máxima
    del hogar. Lanza IngresoNoPermitido si no se puede; en ese caso no cambia nada.
    """
    with transaction.atomic():
        actual, elegida = _validar(ficha, actor)
        entrega = actual.cuidador or actual.responsable
        alojamiento = alojar_en_hogar(
            actual,
            elegida.usuario,
            vacunado=vacunado,
            castrado=castrado,
            desparasitado=desparasitado,
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


def cancelar_entrega(ficha, actor):
    """La entrega al hogar elegido no se hizo (1A): la ficha sigue en adopción.

    La postulación del hogar queda descartada, así que se puede elegir otro. Si cancela el
    hogar, se avisa a quien entrega; si no, se avisa al hogar.
    """
    with transaction.atomic():
        actual, elegida = _validar(ficha, actor)
        entrega = actual.cuidador or actual.responsable
        elegida.estado = Postulacion.Estado.DESCARTADA
        elegida.save(update_fields=["estado"])
        nombre = actual.nombre or "la mascota"
        if actor.pk == elegida.usuario_id:
            if entrega is not None:
                notificar(
                    entrega,
                    Notificacion.Tipo.RESULTADO_POSTULACION,
                    f"El hogar de tránsito canceló la entrega de {nombre}",
                    MENSAJE_CANCELADA_A_QUIEN_ENTREGA,
                    ficha=actual,
                )
        else:
            notificar(
                elegida.usuario,
                Notificacion.Tipo.RESULTADO_POSTULACION,
                f"La entrega de {nombre} no se concretó",
                MENSAJE_CANCELADA_AL_HOGAR,
                ficha=actual,
            )
    return elegida
