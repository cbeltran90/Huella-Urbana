"""Permisos del panel de administración según el rol de la cuenta."""

from .models import Rol


def es_administrador(request):
    return getattr(request.user, "rol", None) == Rol.ADMINISTRADOR


def es_moderador_o_administrador(request):
    return getattr(request.user, "rol", None) in (Rol.MODERADOR, Rol.ADMINISTRADOR)
