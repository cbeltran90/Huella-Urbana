"""Paso de la eliminación de una cuenta que es de publicaciones."""

from apps.cuentas.eliminacion import al_eliminar_cuenta
from apps.fichas.models import Coincidencia

from .models import Publicacion


@al_eliminar_cuenta
def anonimizar_publicaciones(usuario):
    """Sus publicaciones quedan sin autor, sin descripción ni teléfono y, las vigentes, resueltas.

    Se conservan la ubicación, la fecha, el tipo y la cantidad. Las coincidencias que esperaban
    su decisión se descartan: ya no hay a quién avisar.
    """
    publicaciones = Publicacion.objects.filter(autor=usuario)
    Coincidencia.objects.filter(
        publicacion__autor=usuario, decision_responsable=Coincidencia.Decision.PENDIENTE
    ).update(decision_responsable=Coincidencia.Decision.DESCARTADA)
    publicaciones.filter(estado=Publicacion.Estado.VIGENTE).update(
        estado=Publicacion.Estado.RESUELTA
    )
    publicaciones.update(autor=None, descripcion="", telefono_visible="")
