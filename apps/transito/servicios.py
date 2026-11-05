"""Reglas del hogar de tránsito que usan otras partes del sistema."""

from .models import PerfilTransito


def es_hogar_de_transito(usuario):
    """True si la persona tiene un perfil de tránsito activo.

    El rol de hogar de tránsito se deriva de eso: no se guarda en "Usuario.rol".
    """
    if not usuario.is_authenticated:
        return False
    return PerfilTransito.objects.filter(usuario=usuario, activo=True).exists()
