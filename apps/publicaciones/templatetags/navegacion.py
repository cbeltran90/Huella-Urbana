from django import template

from apps.publicaciones import vinculacion

register = template.Library()


@register.simple_tag(takes_context=True)
def coincidencias_pendientes(context):
    """Cuántas coincidencias esperan la decisión de quien mira la página."""
    request = context.get("request")
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return 0
    return vinculacion.pendientes_para(usuario).count()
