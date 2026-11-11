"""Postularse para adoptar un animal disponible (CU-28)."""

from django.db import IntegrityError, transaction

from apps.cuentas.models import Domicilio
from apps.cuentas.servicios import esta_suspendido, puede_postularse_a_adoptar
from apps.fichas.models import FichaAnimal
from apps.notificaciones.models import Notificacion
from apps.notificaciones.servicios import notificar
from apps.transito.models import Postulacion
from apps.transito.postulaciones import (
    CONTACTO_MAXIMO,
    ESTADOS_ACTIVOS,
    MENSAJE_CONTACTO_LARGO,
    MENSAJE_CONTACTO_VACIO,
    ContactoInvalido,
    PostulacionNoPermitida,
)

# Disponible para adoptar: en adopción o en tránsito (decisión del grupo).
ESTADOS_DISPONIBLES = (FichaAnimal.Estado.EN_ADOPCION, FichaAnimal.Estado.EN_TRANSITO)

MENSAJE_SUSPENDIDO = "No podés postularte mientras tu cuenta esté suspendida."
MENSAJE_NO_DISPONIBLE = "Este animal ya no busca familia."
MENSAJE_PERFIL_INCOMPLETO = "Para postularte, primero completá tu perfil de hogar y familia."
MENSAJE_ES_RESPONSABLE = "No podés postularte para adoptar a tu propio animal."
MENSAJE_YA_POSTULADO = "Ya te postulaste para este animal."
MOTIVO_NINOS = "En tu hogar hay niños y no sabemos si este animal se lleva bien con ellos."
MOTIVO_ANIMALES = "Tenés mascotas y no sabemos si este animal se lleva bien con otros animales."
MENSAJE_AVISO = "Alguien se postuló para adoptarlo."


def motivo_para_no_postularse(usuario, ficha):
    """Por qué la persona no puede postularse para adoptar este animal, o None si puede.

    Devuelve un par (código, mensaje). Con "perfil_incompleto" la vista lleva a completar el
    perfil de hogar y familia (CU-05); los demás motivos solo se informan.
    """
    if esta_suspendido(usuario):
        return "suspendido", MENSAJE_SUSPENDIDO
    if ficha.estado not in ESTADOS_DISPONIBLES:
        return "ficha_no_disponible", MENSAJE_NO_DISPONIBLE
    if not puede_postularse_a_adoptar(usuario):
        return "perfil_incompleto", MENSAJE_PERFIL_INCOMPLETO
    # Quien lo cuida (lo encontró o lo aloja en tránsito) sí puede postularse para quedárselo.
    if ficha.responsable_id == usuario.pk:
        return "es_responsable", MENSAJE_ES_RESPONSABLE
    activas = Postulacion.objects.filter(ficha=ficha, usuario=usuario, estado__in=ESTADOS_ACTIVOS)
    if activas.exists():
        return "ya_postulado", MENSAJE_YA_POSTULADO
    return None


def advertencias_de_postulacion(usuario, ficha):
    """Por qué el hogar podría no ser compatible con el animal (lista vacía si no hay dudas).

    Es un aviso: no impide postularse. Quien elige lo ve junto a la postulación (CU-28 2B).
    """
    domicilio = Domicilio.objects.filter(usuario=usuario).first()
    if domicilio is None:
        return []
    motivos = []
    if domicilio.hay_ninos and not ficha.compatible_ninos:
        motivos.append(MOTIVO_NINOS)
    if domicilio.mascotas_propias and not ficha.compatible_animales:
        motivos.append(MOTIVO_ANIMALES)
    return motivos


def postular_adopcion(usuario, ficha, contacto):
    """Registra la postulación pendiente para adoptar el animal y la devuelve.

    Lanza PostulacionNoPermitida si la persona no puede postularse y ContactoInvalido si el
    canal de contacto no sirve. En los dos casos no se crea nada.
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
            postulacion = Postulacion.objects.create(
                ficha=ficha,
                usuario=usuario,
                tipo=Postulacion.Tipo.ADOPCION,
                contacto=contacto,
            )
    except IntegrityError:
        # Dos pedidos a la vez: la restricción de la base evita la segunda.
        raise PostulacionNoPermitida("ya_postulado", MENSAJE_YA_POSTULADO) from None
    _avisar_al_cuidador(postulacion)
    return postulacion


def _avisar_al_cuidador(postulacion):
    """Avisa a quien tiene el animal a cargo que alguien quiere adoptarlo.

    Si no hay cuidador con cuenta, o es él quien se postula para quedárselo, no se avisa.
    """
    ficha = postulacion.ficha
    if ficha.cuidador_id is None or ficha.cuidador_id == postulacion.usuario_id:
        return
    animal = ficha.nombre or "El animal que cuidás"
    notificar(
        ficha.cuidador,
        Notificacion.Tipo.POSTULACION_RECIBIDA,
        f"¡{animal} tiene una persona interesada!",
        MENSAJE_AVISO,
        ficha=ficha,
    )
