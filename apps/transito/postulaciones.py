"""Postularse como hogar de tránsito y retirar la postulación."""

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.cuentas.servicios import esta_suspendido
from apps.fichas.models import FichaAnimal

from .models import Alojamiento, PerfilTransito, Postulacion
from .servicios import esta_disponible, incompatibilidades

CONTACTO_MAXIMO = Postulacion._meta.get_field("contacto").max_length
ESTADOS_ACTIVOS = (Postulacion.Estado.PENDIENTE, Postulacion.Estado.ELEGIDA)

MENSAJE_SIN_PERFIL = "Para postularte tenés que completar tu perfil de hogar de tránsito."
MENSAJE_SUSPENDIDO = "No podés postularte mientras tu cuenta esté suspendida."
MENSAJE_EN_PAUSA = "No podés postularte mientras tu hogar esté en pausa."
MENSAJE_NO_EN_ADOPCION = "Este animal ya no está en adopción."
MENSAJE_TIENE_EL_ANIMAL = "No podés postularte para un animal que tenés a tu cargo."
MENSAJE_YA_POSTULADO = "Ya tenés una postulación activa para este animal."
MENSAJE_CONTACTO_VACIO = "Indicá un canal de contacto."
MENSAJE_CONTACTO_LARGO = f"El canal de contacto no puede superar los {CONTACTO_MAXIMO} caracteres."
MENSAJE_NO_ES_SUYA = "Esa postulación no es tuya."
MENSAJE_NO_PENDIENTE = "Solo se puede retirar una postulación pendiente."


class PostulacionNoPermitida(Exception):
    """La persona no puede postularse. "codigo" dice por qué y "mensaje" se puede mostrar."""

    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo = codigo
        self.mensaje = mensaje


class ContactoInvalido(ValueError):
    """El canal de contacto está vacío o es demasiado largo."""


class RetiroPostulacionNoPermitido(ValueError):
    """La postulación no se puede retirar: no es de la persona o ya no está pendiente."""


def _tiene_el_animal(usuario, ficha):
    """True si el animal está a su cargo o es suyo, o si lo aloja hoy como hogar."""
    if usuario.pk in (ficha.cuidador_id, ficha.responsable_id):
        return True
    return Alojamiento.objects.filter(
        ficha=ficha, hogar_id=usuario.pk, fecha_fin_real__isnull=True
    ).exists()


def motivo_para_no_postularse(usuario, ficha, hoy=None):
    """Por qué la persona no puede postularse a esta ficha hoy, o None si puede.

    Devuelve un par (código, mensaje). El cupo no es condición: un hogar con el cupo
    completo puede postularse. La incompatibilidad tampoco: solo
    se advierte (ver advertencias_de_postulacion).
    """
    perfil = PerfilTransito.objects.filter(usuario=usuario, activo=True).first()
    if perfil is None:
        return "sin_perfil", MENSAJE_SIN_PERFIL
    if esta_suspendido(usuario):
        return "suspendido", MENSAJE_SUSPENDIDO
    if not esta_disponible(perfil, hoy or timezone.localdate()):
        return "en_pausa", MENSAJE_EN_PAUSA
    if ficha.estado != FichaAnimal.Estado.EN_ADOPCION:
        return "ficha_no_disponible", MENSAJE_NO_EN_ADOPCION
    if _tiene_el_animal(usuario, ficha):
        return "tiene_el_animal", MENSAJE_TIENE_EL_ANIMAL
    activas = Postulacion.objects.filter(ficha=ficha, usuario=usuario, estado__in=ESTADOS_ACTIVOS)
    if activas.exists():
        return "ya_postulado", MENSAJE_YA_POSTULADO
    return None


def advertencias_de_postulacion(usuario, ficha):
    """Por qué el hogar no es compatible con la ficha (lista vacía si lo es o no tiene perfil).

    Es un aviso: no impide postularse. Quien elige lo ve junto a la postulación.
    """
    perfil = PerfilTransito.objects.filter(usuario=usuario, activo=True).first()
    return incompatibilidades(perfil, ficha) if perfil is not None else []


def postular_transito(usuario, ficha, contacto):
    """Registra la postulación pendiente del hogar a una ficha en adopción y la devuelve.

    Lanza PostulacionNoPermitida si no puede (sin perfil, suspendido, en pausa, la ficha ya no
    está en adopción, el animal está a su cargo o ya está postulado) y ContactoInvalido si
    el canal de contacto no sirve. En ambos casos no se crea nada.
    """
    motivo = motivo_para_no_postularse(usuario, ficha)
    if motivo is not None:
        raise PostulacionNoPermitida(*motivo)
    contacto = (contacto or "").strip()
    if not contacto:
        raise ContactoInvalido(MENSAJE_CONTACTO_VACIO)
    if len(contacto) > CONTACTO_MAXIMO:
        raise ContactoInvalido(MENSAJE_CONTACTO_LARGO)
    try:
        with transaction.atomic():
            return Postulacion.objects.create(
                ficha=ficha,
                usuario=usuario,
                tipo=Postulacion.Tipo.TRANSITO,
                contacto=contacto,
            )
    except IntegrityError:
        # Dos pedidos a la vez: la restricción de la base evita la segunda.
        raise PostulacionNoPermitida("ya_postulado", MENSAJE_YA_POSTULADO) from None


def retirar_postulacion(postulacion, usuario):
    """El hogar retira su postulación pendiente: queda descartada y se devuelve.

    Lanza RetiroPostulacionNoPermitido si la postulación no es de esa persona o ya no está
    pendiente (elegida, descartada o concretada), y no cambia nada.
    """
    with transaction.atomic():
        actual = Postulacion.objects.select_for_update().get(pk=postulacion.pk)
        if actual.usuario_id != usuario.pk:
            raise RetiroPostulacionNoPermitido(MENSAJE_NO_ES_SUYA)
        if actual.estado != Postulacion.Estado.PENDIENTE:
            raise RetiroPostulacionNoPermitido(MENSAJE_NO_PENDIENTE)
        actual.estado = Postulacion.Estado.DESCARTADA
        actual.save(update_fields=["estado"])
    postulacion.estado = actual.estado
    return postulacion
