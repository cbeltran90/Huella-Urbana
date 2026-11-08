"""Pasos de la eliminación de una cuenta que son de fichas."""

from apps.cuentas.eliminacion import al_eliminar_cuenta

from . import servicios
from .models import FichaAnimal


def tiene_adopcion_registrada(ficha):
    """True si la ficha es la de un animal adoptado (tiene una adopción registrada).

    La consulta es del módulo de adopciones. Mientras no exista, ninguna ficha cuenta.
    """
    try:
        from apps.adopcion.servicios import tiene_adopcion_registrada as consulta
    except ImportError:
        return False
    return consulta(ficha)


@al_eliminar_cuenta
def limpiar_fichas(usuario):
    """Borra sus fichas registradas sin adopción y le quita su contacto a las demás.

    Al borrar una ficha se borran sus fotografías (y los archivos). Las fichas con una adopción
    registrada se conservan: la cuenta queda como "eliminada" y esas fichas lo muestran como
    "usuario eliminado". Las fichas en el circuito no llegan hasta acá: impiden eliminar la cuenta.
    """
    propias = FichaAnimal.objects.filter(responsable=usuario, estado=FichaAnimal.Estado.REGISTRADO)
    for ficha in propias:
        if not tiene_adopcion_registrada(ficha):
            servicios.dar_de_baja(ficha)
    FichaAnimal.objects.filter(cuidador=usuario).update(cuidador=None, cuidador_contacto="")
