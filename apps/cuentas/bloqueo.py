"""Respuesta que se da cuando django-axes bloquea los intentos de ingreso."""

from django.conf import settings
from django.shortcuts import render


def respuesta_bloqueo(request, credentials=None, *args, **kwargs):
    """Página en español con código 429 y la espera que indica la configuración."""
    segundos = int(settings.AXES_COOLOFF_TIME.total_seconds())
    contexto = {"minutos": segundos // 60}
    respuesta = render(request, "cuentas/bloqueado.html", contexto, status=429)
    respuesta["Retry-After"] = str(segundos)
    return respuesta
