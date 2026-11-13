"""Acciones de moderación sobre las fotografías."""

from apps.fichas.permisos import es_moderador
from apps.moderacion.auditoria import registrar_accion

MENSAJE_SOLO_MODERADORES = "Solo un moderador o un administrador puede revisar fotografías."


def marcar_revisada(fotografia, moderador):
    """Un moderador revisa una foto marcada y la aprueba.

    Queda anotado quién la revisó, se quita la marca (así vuelve a mostrarse, porque las
    marcadas se ocultan hasta la revisión) y se deja constancia en el registro de acciones,
    con el motivo de la marca. Devuelve False si la foto no estaba marcada y True si la
    aprobó. Lanza PermissionError si quien la revisa no modera.
    """
    if not es_moderador(moderador):
        raise PermissionError(MENSAJE_SOLO_MODERADORES)
    if not fotografia.motivo_revision:
        return False
    motivo = fotografia.get_motivo_revision_display()
    fotografia.revisada_por = moderador
    fotografia.motivo_revision = ""
    fotografia.save(update_fields=["revisada_por", "motivo_revision"])
    registrar_accion(moderador, fotografia, f"Fotografía revisada y aprobada (marca: {motivo}).")
    return True
