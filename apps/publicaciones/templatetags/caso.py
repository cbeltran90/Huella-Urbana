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


@register.inclusion_tag("publicaciones/_confirmar_dueno.html", takes_context=True)
def opciones_de_dueno(context, ficha):
    """Los extravíos vinculados, para confirmar cuál es del dueño (CU-14, extensión 2A)."""
    usuario = context["request"].user
    puede = resolucion.puede_confirmar_dueno(usuario, ficha) and not esta_suspendido(usuario)
    return {"extravios": resolucion.extravios_del_caso(ficha) if puede else []}
