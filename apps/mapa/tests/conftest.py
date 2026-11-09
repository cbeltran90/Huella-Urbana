import pytest
from django.contrib.gis.geos import Point
from model_bakery import baker

from apps.cuentas.models import EstadoCuenta
from apps.publicaciones.models import Publicacion

CENTRO = Point(-68.3040, -54.8025, srid=4326)


@pytest.fixture
def ana(django_user_model):
    return django_user_model.objects.create_user(
        "ana@ejemplo.com", "Ana", "clave-de-prueba-1", estado_cuenta=EstadoCuenta.ACTIVA
    )


def hacer_publicacion(autor, **campos):
    datos = {"tipo": Publicacion.Tipo.EXTRAVIO, "ubicacion": CENTRO, **campos}
    return baker.make(Publicacion, autor=autor, **datos)
