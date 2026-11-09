"""Resolución de un caso de extravío (CU-14)."""

from django.db import transaction

from apps.fichas.models import FichaAnimal
from apps.fichas.permisos import es_cuidador, es_moderador
from apps.fichas.servicios import cambiar_estado

from .listados import TIPOS_PERDIDOS
from .models import Publicacion


def publicaciones_del_caso(ficha):
    """El caso abierto: las publicaciones vigentes de extravío y hallazgo de la ficha."""
    return ficha.publicaciones.filter(estado=Publicacion.Estado.VIGENTE, tipo__in=TIPOS_PERDIDOS)


def puede_resolver(usuario, ficha):
    """El responsable, el autor de una publicación del caso o un moderador (CU-14).

    Si la ficha no tiene un responsable que sea usuario, solo un moderador (extensión 1A).
    """
    if not usuario.is_authenticated or not publicaciones_del_caso(ficha).exists():
        return False
    if es_moderador(usuario):
        return True
    if ficha.responsable_id is None:
        return False
    return (
        ficha.responsable_id == usuario.pk
        or publicaciones_del_caso(ficha).filter(autor=usuario).exists()
    )


@transaction.atomic
def resolver_caso(ficha, usuario):
    """Cierra el caso: pasa a resueltas sus publicaciones de extravío y hallazgo.

    Siguen vinculadas a la ficha, como parte de su historia. Devuelve cuántas se resolvieron.
    """
    if not puede_resolver(usuario, ficha):
        raise PermissionError("No podés resolver este caso.")
    return _cerrar(ficha)


def _cerrar(ficha):
    # Fuera del alcance de la primera entrega: registrar el resultado (RF3.6).
    return publicaciones_del_caso(ficha).update(estado=Publicacion.Estado.RESUELTA)


def extravios_del_caso(ficha):
    """Los extravíos vigentes de la ficha publicados por un usuario: su autor puede ser el dueño."""
    return (
        publicaciones_del_caso(ficha)
        .filter(tipo=Publicacion.Tipo.EXTRAVIO, autor__isnull=False)
        .select_related("autor")
    )


def puede_confirmar_dueno(usuario, ficha):
    """Quien tiene al animal a su cargo o un moderador, en una ficha sin responsable con un
    extravío vinculado (CU-14, extensión 2A)."""
    if ficha.estado != FichaAnimal.Estado.SIN_RESPONSABLE:
        return False
    if not extravios_del_caso(ficha).exists():
        return False
    return es_cuidador(usuario, ficha) or es_moderador(usuario)


@transaction.atomic
def confirmar_dueno(ficha, extravio, usuario):
    """El autor del extravío es el dueño: la ficha pasa a registrado con esa persona como
    responsable (transición 4) y el caso se cierra.

    Quien lo tenía a cargo se lo devuelve: deja de estar a su cargo y el plazo de ausencia
    deja de correr.
    """
    if not puede_confirmar_dueno(usuario, ficha):
        raise PermissionError("No podés confirmar al dueño de esta ficha.")
    if not extravios_del_caso(ficha).filter(pk=extravio.pk).exists():
        raise ValueError("Ese extravío no es parte del caso de esta ficha.")
    cambiar_estado(
        ficha,
        FichaAnimal.Estado.REGISTRADO,
        actor=usuario,
        cambios={"responsable": extravio.autor, "cuidador": None, "sin_responsable_desde": None},
    )
    return _cerrar(ficha)
