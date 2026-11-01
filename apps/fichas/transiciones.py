from .models import FichaAnimal

E = FichaAnimal.Estado


class TransicionInvalida(Exception):
    """Se pidió un cambio de estado que el modelo de estados no permite."""


# Estados con los que puede nacer una ficha (transiciones 1, 2 y 3)
ESTADOS_INICIALES = frozenset({E.REGISTRADO, E.SIN_RESPONSABLE, E.EN_ADOPCION})

# (estado de origen, estado de destino) -> transición válida
TRANSICIONES = {
    (E.SIN_RESPONSABLE, E.REGISTRADO): (4, 5),  # aparece el dueño / se que con el animal
    (E.SIN_RESPONSABLE, E.EN_ADOPCION): (6,),  # ausencia de responsable o solicitud de tránsito
    (E.REGISTRADO, E.EN_ADOPCION): (10, 11),  # devolución / ofrecimiento
    (E.EN_ADOPCION, E.REGISTRADO): (9, 12, 15),  # adopción / aparece el dueño / retiro
    (E.EN_ADOPCION, E.EN_TRANSITO): (7, 14),  # concreción del tránsito / extensión de plazo
    (E.EN_TRANSITO, E.EN_ADOPCION): (8,),  # relevo o vencimiento del plazo
    (E.EN_TRANSITO, E.REGISTRADO): (13,),  # aparece el dueño
}


def estado_inicial_permitido(estado):
    return estado in ESTADOS_INICIALES


def transicion_permitida(origen, destino):
    return (origen, destino) in TRANSICIONES
