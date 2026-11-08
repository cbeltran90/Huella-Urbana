from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

from apps.cuentas.models import Rol
from apps.fichas.comparacion import buscar_candidatas
from apps.fichas.models import Coincidencia
from apps.fichas.permisos import es_moderador
from apps.imagenes.models import Fotografia

from .models import Publicacion


def _notificar(usuario, titulo, mensaje, publicacion):
    """Avisa por el módulo de notificaciones si ya existe; si no, no hace nada."""
    try:
        from apps.notificaciones.servicios import notificar
    except ImportError:
        return
    notificar(
        usuario, "vinculacion", titulo, mensaje, ficha=publicacion.ficha, publicacion=publicacion
    )


def decisores(ficha):
    """Quiénes pueden confirmar o descartar una coincidencia sobre la ficha.

    El responsable; si no tiene, quien la tiene a cargo y los moderadores.
    """
    if ficha.responsable_id:
        return [ficha.responsable]
    personas = [ficha.cuidador] if ficha.cuidador_id else []
    moderadores = get_user_model().objects.filter(rol__in=[Rol.MODERADOR, Rol.ADMINISTRADOR])
    return personas + [m for m in moderadores if m not in personas]


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
    """El autor elige una candidata. La decisión queda pendiente de quien decide."""
    if publicacion.autor_id != usuario.pk:
        raise PermissionError("Solo el autor de la publicación puede elegir una candidata.")
    coincidencia = Coincidencia.objects.get(publicacion=publicacion, ficha=ficha)
    coincidencia.elegida_por_autor = True
    coincidencia.decision_responsable = Coincidencia.Decision.PENDIENTE
    coincidencia.save(update_fields=["elegida_por_autor", "decision_responsable"])
    for persona in decisores(ficha):
        _notificar(
            persona,
            "Posible coincidencia",
            "Alguien cree que es el mismo animal. Revisá la publicación.",
            publicacion,
        )
    return coincidencia


@transaction.atomic
def responder(coincidencia, usuario, *, confirmar):
    """Quien decide (responsable, cuidador o moderador) confirma o descarta la coincidencia."""
    ficha = coincidencia.ficha
    if not (usuario in decisores(ficha) or es_moderador(usuario)):
        raise PermissionError("No podés decidir sobre esta coincidencia.")
    if not confirmar:
        coincidencia.decision_responsable = Coincidencia.Decision.DESCARTADA
        coincidencia.save(update_fields=["decision_responsable"])
        return coincidencia

    publicacion = coincidencia.publicacion
    coincidencia.decision_responsable = Coincidencia.Decision.CONFIRMADA
    coincidencia.save(update_fields=["decision_responsable"])
    principal, sobrante = ficha, publicacion.ficha
    # Sobrevive la ficha que tiene responsable (la de quien perdió al animal).
    if sobrante and sobrante.responsable_id and not principal.responsable_id:
        principal, sobrante = sobrante, principal
    if sobrante and sobrante.pk != principal.pk:
        Fotografia.objects.filter(ficha=sobrante).update(ficha=principal)
        Publicacion.objects.filter(ficha=sobrante).update(ficha=principal)
        if sobrante.cuidador_id and not principal.cuidador_id:
            principal.cuidador = sobrante.cuidador
            principal.save(update_fields=["cuidador"])
        sobrante.fusionada_en = principal
        sobrante.save(update_fields=["fusionada_en"])
    publicacion.refresh_from_db()
    if publicacion.autor_id:  # si eliminó su cuenta, no hay a quién avisar
        _notificar(
            publicacion.autor,
            "Coincidencia confirmada",
            "Se confirmó que es el mismo animal.",
            publicacion,
        )
    return coincidencia


def puede_desvincular(publicacion, usuario):
    """El autor, el responsable de la ficha o un moderador."""
    if publicacion.ficha_id is None or not usuario.is_authenticated:
        return False
    return (
        publicacion.autor_id == usuario.pk
        or publicacion.ficha.responsable_id == usuario.pk
        or es_moderador(usuario)
    )


@transaction.atomic
def desvincular(publicacion, usuario):
    """Separa la publicación de su ficha. Queda suelta y el rastro se actualiza."""
    if not puede_desvincular(publicacion, usuario):
        raise PermissionError("No podés desvincular esta publicación.")
    ficha = publicacion.ficha
    Coincidencia.objects.filter(publicacion=publicacion, ficha=ficha).update(
        elegida_por_autor=False, decision_responsable=Coincidencia.Decision.DESCARTADA
    )
    publicacion.ficha = None
    publicacion.save(update_fields=["ficha"])
    return ficha


def pendientes_para(usuario):
    """Coincidencias elegidas por su autor que a esta persona le toca confirmar o descartar.

    Responsable de la ficha; si no tiene, quien la tiene a cargo; los moderadores ven las
    de fichas sin responsable (mismas reglas que "decisores").
    """
    if not usuario.is_authenticated:
        return Coincidencia.objects.none()
    filtro = Q(ficha__responsable=usuario) | Q(
        ficha__responsable__isnull=True, ficha__cuidador=usuario
    )
    if es_moderador(usuario):
        filtro |= Q(ficha__responsable__isnull=True)
    return (
        Coincidencia.objects.filter(
            filtro,
            elegida_por_autor=True,
            decision_responsable=Coincidencia.Decision.PENDIENTE,
        )
        .exclude(publicacion__estado=Publicacion.Estado.ELIMINADA)
        .select_related("ficha", "publicacion__autor", "publicacion__ficha")
        .order_by("-id")
    )
