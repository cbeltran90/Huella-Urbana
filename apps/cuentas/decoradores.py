"""Decoradores de permisos para las vistas de otros módulos."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from . import servicios


def cuenta_habilitada(vista):
    """Para las vistas que publican o registran algo (reemplaza a "login_required").

    Un visitante va al ingreso. Una cuenta con sanción vigente recibe una página 403
    que le explica la suspensión: queda con los permisos de un visitante (CU-59).
    """

    @wraps(vista)
    def envuelta(request, *args, **kwargs):
        sancion = servicios.sancion_vigente(request.user)
        if sancion is not None:
            return render(request, "cuentas/suspendida.html", {"sancion": sancion}, status=403)
        return vista(request, *args, **kwargs)

    return login_required(envuelta)
