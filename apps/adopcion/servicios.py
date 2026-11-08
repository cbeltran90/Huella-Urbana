from .models import Adopcion


def tiene_adopcion_registrada(ficha):
    """True si la ficha es la de un animal adoptado (tiene una adopción registrada).

    Por ahora alcanza con que exista una Adopcion de la ficha. Cuando exista Devolucion,
    una adopción devuelta deja de contar: se ajusta solo acá.
    """
    return Adopcion.objects.filter(ficha=ficha).exists()
