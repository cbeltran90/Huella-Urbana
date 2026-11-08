import pytest

from apps.cuentas.models import EstadoCuenta

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
