import pytest
from django.contrib.gis.geos import Point
from django.db import IntegrityError, transaction

from apps.cuentas.models import Domicilio, EstadoCuenta, Usuario

CLAVE = "clave-de-prueba-1"
EXACTO = Point(-68.3030, -54.8019, srid=4326)
DESPLAZADO = Point(-68.3040, -54.8025, srid=4326)


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def crear(usuario, **campos):
    return Domicilio.objects.create(
        usuario=usuario, ubicacion=EXACTO, ubicacion_desplazada=DESPLAZADO, **campos
    )


@pytest.mark.django_db
def test_se_guardan_el_punto_exacto_y_el_desplazado(ana):
    crear(ana)
    domicilio = Domicilio.objects.get(usuario=ana)
    assert domicilio.ubicacion.equals_exact(EXACTO, 1e-9)
    assert domicilio.ubicacion_desplazada.equals_exact(DESPLAZADO, 1e-9)


@pytest.mark.django_db
def test_la_direccion_es_opcional(ana):
    assert crear(ana).direccion == ""


@pytest.mark.django_db
def test_se_accede_desde_el_usuario(ana):
    domicilio = crear(ana, direccion="Calle de prueba 123")
    assert ana.domicilio == domicilio


@pytest.mark.django_db
def test_un_usuario_tiene_un_solo_domicilio(ana):
    crear(ana)
    with pytest.raises(IntegrityError), transaction.atomic():
        crear(ana)


@pytest.mark.django_db
def test_el_domicilio_se_elimina_con_la_cuenta(ana):
    crear(ana)
    ana.delete()
    assert not Domicilio.objects.exists()
