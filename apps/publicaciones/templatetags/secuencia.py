from django import template

from apps.publicaciones import listados

register = template.Library()


@register.inclusion_tag("publicaciones/_secuencia.html")
def secuencia_de_publicaciones(ficha):
    """La secuencia de publicaciones de una ficha, para su detalle."""
    return {"publicaciones": listados.secuencia(ficha)}
