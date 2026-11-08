"""Eliminar la cuenta: qué lo impide y cómo se elimina."""

from dataclasses import dataclass

from django.db.models import Q
from django.utils import timezone

from apps.fichas.models import FichaAnimal
from apps.transito import servicios as servicios_transito

from .models import Sancion
from .servicios import sancion_vigente

MENSAJE_SUSPENSION_TEMPORAL = "No podés eliminar tu cuenta mientras dure la suspensión."
MENSAJE_FICHAS_EN_CIRCUITO = (
    "No podés eliminar tu cuenta mientras tengas animales en el circuito de adopción o "
    "tránsito. Primero resolvé esos casos."
)
MENSAJE_ELECCION_PENDIENTE = (
    "No podés eliminar tu cuenta hasta que se concrete o se cancele la entrega pendiente."
)


@dataclass(frozen=True)
class Impedimento:
    """Un motivo por el que la cuenta no se puede eliminar todavía.

    "codigo" lo identifica, "mensaje" está pensado para mostrarse, "fichas" lista las fichas
    que hay que resolver y "fin" es cuándo termina la suspensión, si ese es el motivo.
    """

    codigo: str
    mensaje: str
    fichas: tuple = ()
    fin: object = None


def mensaje_suspension_temporal(fin):
    return f"{MENSAJE_SUSPENSION_TEMPORAL} Termina el {timezone.localtime(fin):%d/%m/%Y %H:%M}."


def fichas_en_circuito(usuario):
    """Las fichas que impiden eliminar la cuenta.

    Son las que están en adopción o en tránsito y de las que la persona es responsable o
    quien las tiene a cargo, y las sin responsable que tiene a su cargo.
    """
    estados = [FichaAnimal.Estado.EN_ADOPCION, FichaAnimal.Estado.EN_TRANSITO]
    en_circuito = Q(estado__in=estados) & (Q(responsable=usuario) | Q(cuidador=usuario))
    sin_responsable = Q(estado=FichaAnimal.Estado.SIN_RESPONSABLE, cuidador=usuario)
    return tuple(FichaAnimal.objects.filter(en_circuito | sin_responsable).order_by("id"))


def impedimentos_para_eliminar(usuario):
    """Todo lo que impide eliminar la cuenta hoy. Vacío si se puede.

    Una suspensión permanente no impide: es justamente lo único que la persona puede hacer
    """
    impedimentos = []
    sancion = sancion_vigente(usuario)
    if sancion is not None and sancion.tipo == Sancion.Tipo.TEMPORAL:
        impedimentos.append(
            Impedimento(
                "suspension_temporal", mensaje_suspension_temporal(sancion.fin), fin=sancion.fin
            )
        )
    fichas = fichas_en_circuito(usuario)
    if fichas or servicios_transito.tiene_animales_a_cargo(usuario):
        impedimentos.append(
            Impedimento("fichas_en_circuito", MENSAJE_FICHAS_EN_CIRCUITO, fichas=fichas)
        )
    if servicios_transito.tiene_eleccion_pendiente(usuario):
        impedimentos.append(Impedimento("eleccion_pendiente", MENSAJE_ELECCION_PENDIENTE))
    return impedimentos
