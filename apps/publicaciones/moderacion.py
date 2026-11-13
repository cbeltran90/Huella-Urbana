"""Acciones de moderación sobre las publicaciones."""

from django.utils import timezone

from apps.fichas.permisos import es_moderador
from apps.moderacion.auditoria import registrar_accion

from .models import Publicacion

MENSAJE_SOLO_MODERADORES = "Solo un moderador o un administrador puede eliminar publicaciones."


def eliminar_publicacion(publicacion, moderador):
    """Baja lógica de una publicación por moderación.

    Queda en estado "eliminada" con su fecha y se deja constancia en el registro de acciones.
    No se borra nada: la ubicación y los datos se conservan. Devuelve False si ya estaba
    eliminada y True si la eliminó. Lanza PermissionError si quien la pide no modera.
    """
    if not es_moderador(moderador):
        raise PermissionError(MENSAJE_SOLO_MODERADORES)
    if publicacion.estado == Publicacion.Estado.ELIMINADA:
        return False
    publicacion.estado = Publicacion.Estado.ELIMINADA
    publicacion.fecha_eliminacion = timezone.now()
    publicacion.save(update_fields=["estado", "fecha_eliminacion"])
    registrar_accion(moderador, publicacion, "Publicación eliminada por moderación.")
    return True
