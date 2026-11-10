from django import template

from apps.cuentas.servicios import esta_suspendido
from apps.fichas import permisos
from apps.fichas.models import FichaAnimal
from apps.transito import solicitud

register = template.Library()


@register.inclusion_tag("transito/_solicitar.html", takes_context=True)
def boton_solicitar_transito(context, ficha):
    """En la ficha: el botón «Solicitar tránsito», solo para quien puede pedirlo.

    Después de confirmar, quien lo pidió ve un aviso de que la ficha pasó a en adopción.
    """
    request = context["request"]
    usuario = request.user
    habilitado = usuario.is_authenticated and not esta_suspendido(usuario)
    return {
        "ficha": ficha,
        "puede": habilitado and solicitud.puede_solicitar(usuario, ficha),
        "solicitado": (
            habilitado
            and request.GET.get("solicitado") == "1"
            and ficha.estado == FichaAnimal.Estado.EN_ADOPCION
            and permisos.puede_editar(usuario, ficha)
        ),
    }
