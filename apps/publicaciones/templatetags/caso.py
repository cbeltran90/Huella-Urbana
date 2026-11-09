from django import template

from apps.cuentas.servicios import esta_suspendido
from apps.publicaciones import resolucion

register = template.Library()


@register.inclusion_tag("publicaciones/_resolver_caso.html", takes_context=True)
def boton_resolver_caso(context, ficha):
    """El botón para cerrar el caso de extravío, solo para quien puede (CU-14)."""
    usuario = context["request"].user
    puede = resolucion.puede_resolver(usuario, ficha) and not esta_suspendido(usuario)
    return {"ficha": ficha, "puede": puede}
