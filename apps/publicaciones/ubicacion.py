"""De dónde sale el punto de una publicación.

El domicilio y su punto desplazado los calcula y guarda "apps.cuentas". Solo se
usa el punto DESPLAZADO: el exacto ("Domicilio.ubicacion") nunca se lee ni se publica.
"""

from apps.cuentas.models import Domicilio
from apps.cuentas.servicios import guardar_domicilio


def punto_de_domicilio(usuario):
    """Punto desplazado del domicilio del usuario, o None si no tiene."""
    domicilio = Domicilio.objects.filter(usuario=usuario).first()
    return domicilio.ubicacion_desplazada if domicilio else None


def registrar_domicilio(usuario, punto):
    """Guarda "punto" como domicilio del usuario y devuelve el punto desplazado.

    Lanza "DomicilioInvalido" (de cuentas) si el punto está fuera de la zona.
    """
    return guardar_domicilio(usuario, punto).ubicacion_desplazada
