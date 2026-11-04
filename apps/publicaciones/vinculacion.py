from django.db import transaction

from apps.fichas.comparacion import buscar_candidatas
from apps.fichas.models import Coincidencia
from apps.imagenes.models import Fotografia


def _notificar(usuario, titulo, mensaje, publicacion):
    """Avisa por el módulo de notificaciones si ya existe; si no, no hace nada."""
    try:
        from apps.notificaciones.servicios import notificar
    except ImportError:
        return
    notificar(
        usuario, "coincidencia", titulo, mensaje, ficha=publicacion.ficha, publicacion=publicacion
    )


@transaction.atomic
def proponer_coincidencias(publicacion):
    """Guarda (o actualiza) las candidatas de la publicación y las devuelve."""
    guardadas = []
    for ficha, atributos, similitud in buscar_candidatas(publicacion):
        coincidencia, _ = Coincidencia.objects.update_or_create(
            publicacion=publicacion,
            ficha=ficha,
            defaults={"atributos_coincidentes": atributos, "similitud_visual": similitud},
        )
        guardadas.append(coincidencia)
    return guardadas


@transaction.atomic
def vincular(publicacion, ficha, usuario):
    """El autor elige una candidata. La decisión queda pendiente del responsable."""
    if publicacion.autor_id != usuario.pk:
        raise PermissionError("Solo el autor de la publicación puede elegir una candidata.")
    coincidencia = Coincidencia.objects.get(publicacion=publicacion, ficha=ficha)
    coincidencia.elegida_por_autor = True
    coincidencia.decision_responsable = Coincidencia.Decision.PENDIENTE
    coincidencia.save(update_fields=["elegida_por_autor", "decision_responsable"])
    if ficha.responsable_id:
        _notificar(
            ficha.responsable,
            "Posible coincidencia",
            "Alguien cree haber encontrado a tu animal. Revisá la publicación.",
            publicacion,
        )
    return coincidencia


@transaction.atomic
def responder(coincidencia, usuario, *, confirmar):
    """El responsable de la ficha confirma o descarta la coincidencia."""
    ficha = coincidencia.ficha
    if ficha.responsable_id != usuario.pk:
        raise PermissionError("Solo el responsable de la ficha decide.")
    if not confirmar:
        coincidencia.decision_responsable = Coincidencia.Decision.DESCARTADA
        coincidencia.save(update_fields=["decision_responsable"])
        return coincidencia
    publicacion = coincidencia.publicacion
    sobrante = publicacion.ficha
    coincidencia.decision_responsable = Coincidencia.Decision.CONFIRMADA
    coincidencia.save(update_fields=["decision_responsable"])
    if sobrante and sobrante.pk != ficha.pk:
        Fotografia.objects.filter(ficha=sobrante).update(ficha=ficha)
        sobrante.fusionada_en = ficha
        sobrante.save(update_fields=["fusionada_en"])
    publicacion.ficha = ficha
    publicacion.save(update_fields=["ficha"])
    _notificar(
        publicacion.autor,
        "Coincidencia confirmada",
        "El responsable confirmó que es su animal.",
        publicacion,
    )
    return coincidencia
