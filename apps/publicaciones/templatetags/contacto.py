from django import template

from apps.publicaciones.models import Publicacion
from apps.publicaciones.telefonos import enlace_whatsapp

register = template.Library()


@register.inclusion_tag("publicaciones/_telefono.html")
def telefono_de_contacto(publicacion):
    """El teléfono que dejó quien publica, mientras la publicación sigue abierta."""
    telefono = publicacion.telefono_visible
    if publicacion.estado != Publicacion.Estado.VIGENTE:
        telefono = ""
    return {"telefono": telefono, "whatsapp": enlace_whatsapp(telefono)}
