import pytest

from apps.cuentas.models import EstadoCuenta, Rol

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"


def _crear(django_user_model, nombre, rol=Rol.REGISTRADO):
    return django_user_model.objects.create_user(
        f"{nombre.lower()}@ejemplo.com",
        nombre,
        CLAVE,
        estado_cuenta=EstadoCuenta.ACTIVA,
        rol=rol,
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


@pytest.fixture
def moderador(django_user_model):
    return _crear(django_user_model, "Moderador", rol=Rol.MODERADOR)


@pytest.fixture
def entrar(client):
    """Devuelve una función que inicia sesión con un usuario y entrega el cliente."""

    def _entrar(usuario):
        client.force_login(usuario, backend=BACKEND_MODELO)
        return client

    return _entrar
