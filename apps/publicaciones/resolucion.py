"""Resolución de un caso de extravío (CU-14)."""

from django.db import transaction

from apps.fichas.permisos import es_moderador

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
    # Fuera del alcance de la primera entrega: registrar el resultado (RF3.6).
    return publicaciones_del_caso(ficha).update(estado=Publicacion.Estado.RESUELTA)
