"""Eliminar la cuenta: qué lo impide y cómo se elimina."""

from dataclasses import dataclass

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.fichas.models import FichaAnimal
from apps.transito import servicios as servicios_transito

from .models import Domicilio, EstadoCuenta, PerfilAdoptante, Rol, Sancion, Usuario
from .servicios import sancion_vigente

MENSAJE_SUSPENSION_TEMPORAL = "No podés eliminar tu cuenta mientras dure la suspensión."
MENSAJE_FICHAS_EN_CIRCUITO = (
    "No podés eliminar tu cuenta mientras tengas mascotas en el circuito de adopción o "
    "tránsito. Primero resolvé esos casos."
)
MENSAJE_ELECCION_PENDIENTE = (
    "No podés eliminar tu cuenta hasta que se concrete o se cancele la entrega pendiente."
)
MENSAJE_ULTIMO_ADMINISTRADOR = (
    "No podés eliminar tu cuenta porque sos el único administrador activo. "
    "Primero asigná el rol de administrador a otra persona."
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


class EliminacionNoPermitida(Exception):
    """La cuenta todavía no se puede eliminar. "impedimentos" dice por qué."""

    def __init__(self, impedimentos):
        super().__init__(" ".join(impedimento.mensaje for impedimento in impedimentos))
        self.impedimentos = impedimentos


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


def es_ultimo_administrador(usuario):
    """True si es administrador y no queda otro con la cuenta activa."""
    if usuario.rol != Rol.ADMINISTRADOR:
        return False
    otros = Usuario.objects.filter(rol=Rol.ADMINISTRADOR, estado_cuenta=EstadoCuenta.ACTIVA)
    return not otros.exclude(pk=usuario.pk).exists()


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
    if es_ultimo_administrador(usuario):
        impedimentos.append(Impedimento("ultimo_administrador", MENSAJE_ULTIMO_ADMINISTRADOR))
    fichas = fichas_en_circuito(usuario)
    if fichas or servicios_transito.tiene_animales_a_cargo(usuario):
        impedimentos.append(
            Impedimento("fichas_en_circuito", MENSAJE_FICHAS_EN_CIRCUITO, fichas=fichas)
        )
    if servicios_transito.tiene_eleccion_pendiente(usuario):
        impedimentos.append(Impedimento("eleccion_pendiente", MENSAJE_ELECCION_PENDIENTE))
    return impedimentos


# Pasos de la eliminación que son de otros módulos. Cada uno se registra
# con "al_eliminar_cuenta" y se ejecuta dentro de la misma transacción.
_LIMPIEZAS = []


def al_eliminar_cuenta(funcion):
    """Registra un paso que se ejecuta al eliminar una cuenta.

    La función recibe la cuenta que se elimina y corre dentro de la transacción: si lanza un
    error, no se elimina nada. Se usa como decorador.
    """
    _LIMPIEZAS.append(funcion)
    return funcion


def _vaciar_datos_propios(usuario):
    """Paso 5: domicilio y datos del hogar (se borran) y perfiles (la fila queda sin datos)."""
    Domicilio.objects.filter(usuario=usuario).delete()
    PerfilAdoptante.objects.filter(usuario=usuario).update(experiencia_previa="")
    servicios_transito.vaciar_perfil_transito(usuario)


def _marcar_eliminada(usuario):
    """Paso 9: la cuenta queda eliminada, sin nombre ni correo y sin poder entrar.

    La fila se conserva (la usan las fichas adoptadas, las sanciones y los registros). El
    nombre y el correo se reemplazan por valores únicos, que además dejan libres los
    originales.
    """
    usuario.nombre_usuario = f"usuario-eliminado-{usuario.pk}"
    usuario.email = f"eliminada-{usuario.pk}@eliminada.invalid"
    usuario.rol = Rol.REGISTRADO
    usuario.estado_cuenta = EstadoCuenta.ELIMINADA
    usuario.set_unusable_password()
    usuario.save()


def eliminar_cuenta(usuario):
    """Elimina la cuenta y devuelve la cuenta ya eliminada.

    Vuelve a verificar los impedimentos dentro de la transacción: si hay alguno lanza
    EliminacionNoPermitida y no cambia nada. Si la cuenta ya estaba eliminada, no hace nada.

    Conserva el hash del correo y las sanciones, que usa la detección de reincidencia
    el hash vive en cada sanción. Los pasos 6 a 8 son de otros módulos y se
    enganchan con "al_eliminar_cuenta".
    """
    with transaction.atomic():
        # Se bloquea la cuenta para que dos pedidos a la vez no se pisen.
        usuario = Usuario.objects.select_for_update().get(pk=usuario.pk)
        if usuario.estado_cuenta == EstadoCuenta.ELIMINADA:
            return usuario
        impedimentos = impedimentos_para_eliminar(usuario)
        if impedimentos:
            raise EliminacionNoPermitida(impedimentos)
        _vaciar_datos_propios(usuario)
        for limpieza in _LIMPIEZAS:
            limpieza(usuario)
        _marcar_eliminada(usuario)
    return usuario
