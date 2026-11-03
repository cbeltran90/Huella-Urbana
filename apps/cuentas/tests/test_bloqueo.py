import pytest
from django.urls import reverse

from apps.cuentas.models import EstadoCuenta, Usuario

CLAVE = "clave-de-prueba-1"
INCORRECTA = "otra-clave-equivocada"


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def intentar(client, clave, email="ana@example.com"):
    return client.post(reverse("cuentas:login"), {"username": email, "password": clave})


def fallar(client, veces):
    return [intentar(client, INCORRECTA).status_code for _ in range(veces)]


@pytest.mark.django_db
def test_cuatro_fallos_todavia_no_bloquean(client, ana):
    assert fallar(client, 4) == [200, 200, 200, 200]


@pytest.mark.django_db
def test_cinco_fallos_bloquean_con_una_pagina_en_espanol(client, ana):
    fallar(client, 5)
    respuesta = intentar(client, INCORRECTA)
    contenido = respuesta.content.decode()
    assert respuesta.status_code == 429
    assert "Demasiados intentos fallidos" in contenido
    assert "15 minutos" in contenido
    assert respuesta["Retry-After"] == "900"


@pytest.mark.django_db
def test_con_el_bloqueo_activo_ni_la_clave_correcta_entra(client, ana):
    fallar(client, 5)
    respuesta = intentar(client, CLAVE)
    assert respuesta.status_code == 429
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_un_ingreso_correcto_reinicia_el_contador(client, ana):
    fallar(client, 4)
    assert intentar(client, CLAVE).status_code == 302
    client.logout()
    assert fallar(client, 4) == [200, 200, 200, 200]
