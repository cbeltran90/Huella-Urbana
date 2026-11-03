from datetime import timedelta
from functools import wraps

from constance import config
from django.http import HttpResponseForbidden
from django.utils import timezone


def limite_publicaciones(vista):
    """Decorador para las vistas que crean publicaciones.

    Si el usuario ya hizo "MAX_PUBLICACIONES_HORA" en la última hora, responde 403.
    Solo mira los POST: abrir el formulario no cuenta.
    """

    @wraps(vista)
    def envuelta(request, *args, **kwargs):
        if request.method == "POST" and request.user.is_authenticated:
            # Import acá: apps.core no puede depender de publicaciones al cargarse.
            from apps.publicaciones.models import Publicacion

            desde = timezone.now() - timedelta(hours=1)
            hechas = Publicacion.objects.filter(autor=request.user, fecha__gte=desde).count()
            if hechas >= config.MAX_PUBLICACIONES_HORA:
                return HttpResponseForbidden("Alcanzaste el límite de publicaciones por hora")
        return vista(request, *args, **kwargs)

    return envuelta
