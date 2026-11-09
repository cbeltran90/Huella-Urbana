"""Capas del mapa interactivo (CU-19, RF3.1)."""

from apps.publicaciones.listados import TIPOS_PERDIDOS
from apps.publicaciones.models import Publicacion

Tipo = Publicacion.Tipo

# Una capa junta los tipos que comparten contenido y regla de vigencia.
# Los avistamientos peligrosos y los comederos se suman cuando existan sus datos.
CAPAS = {
    "perdidos": TIPOS_PERDIDOS,
    "adopcion": (Tipo.ADOPCION, Tipo.TRANSITO),
}
_CAPA_DE = {tipo: capa for capa, tipos in CAPAS.items() for tipo in tipos}


def geojson():
    """Las publicaciones vigentes de todas las capas, como FeatureCollection de GeoJSON."""
    publicaciones = Publicacion.objects.filter(
        estado=Publicacion.Estado.VIGENTE, tipo__in=list(_CAPA_DE)
    ).values_list("pk", "tipo", "ubicacion")
    return {
        "type": "FeatureCollection",
        "features": [_punto(pk, tipo, ubicacion) for pk, tipo, ubicacion in publicaciones],
    }


def _punto(pk, tipo, ubicacion):
    # GeoJSON va en [longitud, latitud]. Con seis decimales (unos 10 cm) alcanza.
    coordenadas = [round(ubicacion.x, 6), round(ubicacion.y, 6)]
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": coordenadas},
        "properties": {"id": pk, "tipo": tipo, "capa": _CAPA_DE[tipo]},
    }
