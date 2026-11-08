"""Cuando se elimina una cuenta notificaciones borra sus avisos."""

from apps.cuentas.eliminacion import al_eliminar_cuenta

from .models import Notificacion


@al_eliminar_cuenta
def borrar_notificaciones(usuario):
    """Paso 6: se borran todas sus notificaciones (la cuenta se conserva, el CASCADE no actúa)."""
    Notificacion.objects.filter(usuario=usuario).delete()
