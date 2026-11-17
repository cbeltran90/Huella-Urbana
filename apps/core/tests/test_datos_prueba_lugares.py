from apps.core.datos_prueba.lugares import LUGARES, punto
from apps.cuentas import geo


def test_todos_los_lugares_estan_en_la_zona():
    afuera = [clave for clave, lugar in LUGARES.items() if not geo.en_zona(lugar.lon, lugar.lat)]
    assert afuera == []


def test_no_hay_dos_lugares_en_el_mismo_punto():
    puntos = {(lugar.lon, lugar.lat) for lugar in LUGARES.values()}
    assert len(puntos) == len(LUGARES)


def test_punto_devuelve_longitud_y_latitud_en_ese_orden():
    centro = punto("centro")
    assert (centro.x, centro.y, centro.srid) == (-68.31129, -54.80670, 4326)
