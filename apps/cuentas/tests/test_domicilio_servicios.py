import math

import pytest
from constance.test import override_config
from django.contrib.gis.geos import Point

from apps.cuentas import geo, servicios
from apps.cuentas.models import Domicilio, EstadoCuenta, Usuario
from apps.publicaciones import ubicacion

CLAVE = "clave-de-prueba-1"
EXACTO = Point(-68.3030, -54.8019, srid=4326)
OTRO = Point(-68.3100, -54.8100, srid=4326)
BUENOS_AIRES = Point(-58.3816, -34.6037, srid=4326)


class AzarFijo:
    """Devuelve los valores dados, en orden, en lugar de números al azar."""

    def __init__(self, *valores):
        self.valores = iter(valores)

    def random(self):
        return next(self.valores)


def metros(a, b):
    """Distancia en metros entre dos puntos (fórmula de haversine)."""
    f1, f2 = math.radians(a.y), math.radians(b.y)
    h = (
        math.sin((f2 - f1) / 2) ** 2
        + math.cos(f1) * math.cos(f2) * math.sin(math.radians(b.x - a.x) / 2) ** 2
    )
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


# --- geo ---


def test_desplazar_con_valores_fijos_va_hacia_el_norte():
    lon, lat = geo.desplazar(-68.3, -54.8, 150, AzarFijo(1.0, 0.0))
    assert lon == -68.3
    assert lat == pytest.approx(-54.8 + 150 / 111_320)


def test_desplazar_nunca_se_pasa_del_radio():
    for _ in range(300):
        lon, lat = geo.desplazar(EXACTO.x, EXACTO.y, 150)
        assert metros(EXACTO, Point(lon, lat)) <= 150


def test_la_zona_incluye_ushuaia_y_excluye_el_resto_del_pais():
    assert geo.en_zona(-68.30, -54.80)
    assert not geo.en_zona(BUENOS_AIRES.x, BUENOS_AIRES.y)
    assert not geo.en_zona(-67.70, -53.80)  # Río Grande


# --- guardar_domicilio ---


@pytest.mark.django_db
def test_guarda_el_exacto_y_un_desplazado_a_menos_de_150_metros(ana):
    domicilio = servicios.guardar_domicilio(ana, EXACTO)

    domicilio.refresh_from_db()
    assert domicilio.ubicacion.equals_exact(EXACTO, 1e-9)
    assert not domicilio.ubicacion_desplazada.equals_exact(EXACTO, 1e-9)
    assert metros(domicilio.ubicacion, domicilio.ubicacion_desplazada) <= 150


@pytest.mark.django_db
@override_config(RADIO_DOMICILIO_METROS=50)
def test_el_radio_sale_del_parametro(ana):
    domicilio = servicios.guardar_domicilio(ana, EXACTO)
    assert metros(domicilio.ubicacion, domicilio.ubicacion_desplazada) <= 50


@pytest.mark.django_db
def test_guardar_el_mismo_punto_conserva_el_desplazado(ana):
    primero = servicios.guardar_domicilio(ana, EXACTO)
    desplazado = primero.ubicacion_desplazada

    segundo = servicios.guardar_domicilio(ana, EXACTO)

    assert segundo.ubicacion_desplazada.equals_exact(desplazado, 1e-9)
    assert Domicilio.objects.count() == 1


@pytest.mark.django_db
def test_un_punto_nuevo_cambia_el_exacto_y_el_desplazado(ana):
    primero = servicios.guardar_domicilio(ana, EXACTO)
    desplazado = primero.ubicacion_desplazada

    segundo = servicios.guardar_domicilio(ana, OTRO)

    assert segundo.ubicacion.equals_exact(OTRO, 1e-9)
    assert not segundo.ubicacion_desplazada.equals_exact(desplazado, 1e-9)
    assert metros(segundo.ubicacion, segundo.ubicacion_desplazada) <= 150
    assert Domicilio.objects.count() == 1


@pytest.mark.django_db
def test_un_punto_fuera_de_ushuaia_se_rechaza(ana):
    with pytest.raises(servicios.DomicilioInvalido) as error:
        servicios.guardar_domicilio(ana, BUENOS_AIRES)
    assert str(error.value) == servicios.MENSAJE_FUERA_DE_ZONA
    assert not Domicilio.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("punto", [None, "-68.3,-54.8", Point()])
def test_sin_un_punto_valido_se_rechaza(ana, punto):
    with pytest.raises(servicios.DomicilioInvalido):
        servicios.guardar_domicilio(ana, punto)


@pytest.mark.django_db
def test_un_punto_sin_srid_se_toma_como_4326(ana):
    domicilio = servicios.guardar_domicilio(ana, Point(EXACTO.x, EXACTO.y))
    assert domicilio.ubicacion.srid == 4326
    assert domicilio.ubicacion.equals_exact(EXACTO, 1e-9)


@pytest.mark.django_db
def test_un_punto_en_otro_sistema_de_coordenadas_se_convierte(ana):
    en_metros = EXACTO.transform(3857, clone=True)
    domicilio = servicios.guardar_domicilio(ana, en_metros)
    assert domicilio.ubicacion.srid == 4326
    assert domicilio.ubicacion.x == pytest.approx(EXACTO.x, abs=1e-6)
    assert domicilio.ubicacion.y == pytest.approx(EXACTO.y, abs=1e-6)


# --- contrato con el módulo de publicaciones ---


@pytest.mark.django_db
def test_el_modulo_de_publicaciones_usa_este_domicilio(ana):
    assert ubicacion.punto_de_domicilio(ana) is None

    mostrado = ubicacion.registrar_domicilio(ana, EXACTO)

    assert metros(EXACTO, mostrado) <= 150
    assert ubicacion.punto_de_domicilio(ana).equals_exact(mostrado, 1e-9)
    assert Domicilio.objects.get(usuario=ana).ubicacion_desplazada.equals_exact(mostrado, 1e-9)
