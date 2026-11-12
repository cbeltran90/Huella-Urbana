from django import template

from apps.adopcion import eleccion, entrega, postulaciones
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


@register.inclusion_tag("adopcion/_postulantes.html", takes_context=True)
def postulantes_de_adopcion(context, ficha):
    """En la ficha: cuántos se postularon, o la adopción en curso para concretarla (CU-29, CU-30).

    Con alguien elegido lo ve quien puede entregar (también un moderador). Si no, solo quien
    elige.
    """
    usuario = context["request"].user
    if ficha.estado not in postulaciones.ESTADOS_DISPONIBLES:
        return {"mostrar": False}
    elegida = eleccion.elegida_de(ficha)
    if elegida is not None and entrega.puede_entregar(usuario, ficha):
        return {"mostrar": True, "ficha": ficha, "elegida": elegida}
    if not eleccion.puede_elegir(usuario, ficha):
        return {"mostrar": False}
    return {"mostrar": True, "ficha": ficha, "cantidad": eleccion.postulantes_de(ficha).count()}


@register.inclusion_tag("adopcion/_adoptada.html", takes_context=True)
def aviso_de_adopcion(context, ficha):
    """Al volver de concretar la adopción, lo confirma (CU-30). No dice quién adoptó."""
    adoptada = context["request"].GET.get("adoptada") == "1"
    return {"mostrar": adoptada and ficha.adopciones.exists()}
