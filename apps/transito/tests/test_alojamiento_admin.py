import pytest
from django.urls import reverse

from apps.cuentas.models import EstadoCuenta, Rol, Usuario

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"

pytestmark = pytest.mark.django_db


def lista():
    return reverse("admin:transito_alojamiento_changelist")


def entrar(client, rol):
    usuario = Usuario.objects.create_user(
        f"{rol}@example.com", rol.title(), CLAVE, rol=rol, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND_MODELO)


def test_el_moderador_ve_la_lista_de_alojamientos(client):
    entrar(client, Rol.MODERADOR)
    assert client.get(lista()).status_code == 200


def test_una_persona_registrada_no_ve_los_alojamientos(client):
    entrar(client, Rol.REGISTRADO)
    assert client.get(lista()).status_code != 200
