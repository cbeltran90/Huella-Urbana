from django import template

from apps.fichas.models import FichaAnimal
from apps.transito import postulaciones
from apps.transito.models import Postulacion

register = template.Library()

MOTIVOS_QUE_SE_MUESTRAN = ("suspendido", "en_pausa")


@register.inclusion_tag("transito/_postulacion.html", takes_context=True)
def postulacion_de_transito(context, ficha):
    """En la ficha: postularse, ver la postulación o retirarla.

    Solo lo ven los hogares de tránsito, y solo en una ficha en adopción. Un visitante, una
    persona sin perfil de tránsito o quien tiene el animal a su cargo no ven nada.

    Solo muestra la postulación propia de tipo tránsito: la de adopción es de otro panel.
    """
    request = context["request"]
    usuario = request.user
    vacio = {"mostrar": False}
    if not usuario.is_authenticated or ficha.estado != FichaAnimal.Estado.EN_ADOPCION:
        return vacio
    contexto = {
        "mostrar": True,
        "ficha": ficha,
        "csrf_token": context.get("csrf_token"),
        "postulado": request.GET.get("postulado") == "1",
    }
    propia = Postulacion.objects.filter(
        ficha=ficha,
        usuario=usuario,
        tipo=Postulacion.Tipo.TRANSITO,
        estado__in=postulaciones.ESTADOS_ACTIVOS,
    ).first()
    if propia is not None:
        return {**contexto, "propia": propia}
    motivo = postulaciones.motivo_para_no_postularse(usuario, ficha)
    if motivo is None:
        return {**contexto, "puede": True}
    codigo, mensaje = motivo
    if codigo not in MOTIVOS_QUE_SE_MUESTRAN:
        return vacio
    return {**contexto, "motivo": mensaje, "en_pausa": codigo == "en_pausa"}
