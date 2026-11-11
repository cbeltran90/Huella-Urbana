"""Postularse para adoptar un animal disponible (CU-28)."""

from apps.cuentas.servicios import esta_suspendido, puede_postularse_a_adoptar
from apps.fichas.models import FichaAnimal
from apps.transito.models import Postulacion
from apps.transito.postulaciones import ESTADOS_ACTIVOS

# Disponible para adoptar: en adopción o en tránsito (decisión del grupo).
ESTADOS_DISPONIBLES = (FichaAnimal.Estado.EN_ADOPCION, FichaAnimal.Estado.EN_TRANSITO)

MENSAJE_SUSPENDIDO = "No podés postularte mientras tu cuenta esté suspendida."
MENSAJE_NO_DISPONIBLE = "Este animal ya no busca familia."
MENSAJE_PERFIL_INCOMPLETO = "Para postularte, primero completá tu perfil de hogar y familia."
MENSAJE_ES_RESPONSABLE = "No podés postularte para adoptar a tu propio animal."
MENSAJE_YA_POSTULADO = "Ya te postulaste para este animal."


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
