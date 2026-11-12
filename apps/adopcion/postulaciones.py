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
MENSAJE_NO_DISPONIBLE = "Esta mascota ya no busca familia."
MENSAJE_PERFIL_INCOMPLETO = "Para postularte, primero completá tu perfil de hogar y familia."
MENSAJE_ES_RESPONSABLE = "No podés postularte para adoptar a tu propia mascota."
MENSAJE_YA_POSTULADO = "Ya te postulaste para esta mascota."
MOTIVO_NINOS = "En tu hogar hay niños y no sabemos si esta mascota se lleva bien con ellos."
MOTIVO_ANIMALES = "Tenés mascotas y no sabemos si esta mascota se lleva bien con otros animales."
MENSAJE_AVISO = "Alguien quiere darle un hogar."


def motivo_para_no_postularse(usuario, ficha):
    """Por qué la persona no puede postularse para adoptar esta mascota, o None si puede.

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


def advertencias_de_postulacion(usuario, ficha, motivos=(MOTIVO_NINOS, MOTIVO_ANIMALES)):
    """Por qué el hogar podría no ser compatible con la mascota (lista vacía si no hay dudas).

    Es un aviso: no impide postularse. "motivos" son los textos para niños y para otras
    mascotas; por defecto, los de quien se postula.
    """
    domicilio = Domicilio.objects.filter(usuario=usuario).first()
    if domicilio is None:
        return []
    motivo_ninos, motivo_animales = motivos
    dudas = []
    if domicilio.hay_ninos and not ficha.compatible_ninos:
        dudas.append(motivo_ninos)
    if domicilio.mascotas_propias and not ficha.compatible_animales:
        dudas.append(motivo_animales)
    return dudas


def postular_adopcion(usuario, ficha, contacto):
    """Registra la postulación pendiente para adoptar la mascota y la devuelve.

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
    """Avisa a quien tiene la mascota a cargo que alguien quiere adoptarla.

    Si no hay cuidador con cuenta, o es él quien se postula para quedársela, no se avisa.
    """
    ficha = postulacion.ficha
    if ficha.cuidador_id is None or ficha.cuidador_id == postulacion.usuario_id:
        return
    animal = ficha.nombre or "La mascota que cuidás"
    notificar(
        ficha.cuidador,
        Notificacion.Tipo.POSTULACION_RECIBIDA,
        f"¡{animal} tiene una persona interesada!",
        MENSAJE_AVISO,
        ficha=ficha,
    )
