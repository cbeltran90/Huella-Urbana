from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def avisos_sin_leer(context):
    """Cuántos avisos sin leer tiene quien mira la página."""
    request = context.get("request")
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return 0
    return usuario.notificaciones.filter(leida=False).count()
