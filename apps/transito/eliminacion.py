"""Cuando se elimina una cuenta, tránsito borra sus postulaciones."""

from apps.cuentas.eliminacion import al_eliminar_cuenta

from .models import Postulacion


@al_eliminar_cuenta
def borrar_postulaciones(usuario):
    """Paso 6: se borran sus postulaciones, de tránsito y de adopción."""
    Postulacion.objects.filter(usuario=usuario).delete()
