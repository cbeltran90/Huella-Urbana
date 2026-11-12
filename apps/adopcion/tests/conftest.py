import pytest
from django.contrib.gis.geos import Point
from model_bakery import baker

from apps.cuentas import servicios as cuentas
from apps.cuentas.models import Domicilio, EstadoCuenta
from apps.fichas.models import FichaAnimal

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"


def _crear(django_user_model, nombre):
    return django_user_model.objects.create_user(
        f"{nombre.lower()}@ejemplo.com",
        nombre,
        CLAVE,
        estado_cuenta=EstadoCuenta.ACTIVA,
    )


@pytest.fixture
def ana(django_user_model):
    return _crear(django_user_model, "Ana")


@pytest.fixture
def beto(django_user_model):
    return _crear(django_user_model, "Beto")


@pytest.fixture
def carla(django_user_model):
    return _crear(django_user_model, "Carla")


PUNTO = Point(-68.3030, -54.8019, srid=4326)
HOGAR = {
    "tipo_vivienda": "casa",
    "tiene_patio": True,
    "convivientes": 2,
    "hay_ninos": False,
    "mascotas_propias": 0,
}


def con_perfil(usuario, **hogar):
    """La persona con su perfil de hogar y familia completo (CU-05)."""
    Domicilio.objects.create(
        usuario=usuario, ubicacion=PUNTO, ubicacion_desplazada=PUNTO, **{**HOGAR, **hogar}
    )
    cuentas.guardar_perfil_adoptante(usuario, "Tuve perros toda la vida.")
    return usuario


def hacer_ficha(estado=FichaAnimal.Estado.EN_ADOPCION, **campos):
    """Una ficha pública, como las que están en adopción."""
    datos = {"especie": "perro", "es_privada": False, **campos}
    return baker.make(FichaAnimal, estado=estado, **datos)
