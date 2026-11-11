from django import template

from apps.adopcion import postulaciones
from apps.transito.models import Postulacion

register = template.Library()


@register.inclusion_tag("adopcion/_postulacion.html", takes_context=True)
def postulacion_de_adopcion(context, ficha):
    """En la ficha: postularse para adoptar, ver la postulación o retirarla (CU-28).

    Un visitante ve el botón (al tocarlo inicia sesión). No se ve nada si el animal no está
    disponible, si es de quien mira o si tiene una postulación de tránsito activa (esa la
    muestra el panel de tránsito).
    """
    request = context["request"]
    usuario = request.user
    vacio = {"mostrar": False}
    if ficha.estado not in postulaciones.ESTADOS_DISPONIBLES:
        return vacio
    contexto = {
        "mostrar": True,
        "ficha": ficha,
        "csrf_token": context.get("csrf_token"),
        "postulado": request.GET.get("postulado_adopcion") == "1",
    }
    if not usuario.is_authenticated:
        return {**contexto, "puede": True}
    propia = Postulacion.objects.filter(
        ficha=ficha, usuario=usuario, estado__in=postulaciones.ESTADOS_ACTIVOS
    ).first()
    if propia is not None:
        if propia.tipo != Postulacion.Tipo.ADOPCION:
            return vacio
        return {**contexto, "propia": propia}
    motivo = postulaciones.motivo_para_no_postularse(usuario, ficha)
    # Sin perfil también ve el botón: la pantalla le explica qué le falta.
    if motivo is None or motivo[0] == "perfil_incompleto":
        return {**contexto, "puede": True}
    if motivo[0] == "suspendido":
        return {**contexto, "motivo": motivo[1]}
    return vacio
