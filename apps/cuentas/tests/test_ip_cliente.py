"""La IP que ve django-axes es la del visitante y no la de Caddy"""

import pytest
from axes.helpers import get_client_ip_address
from django.test import RequestFactory
from django.urls import reverse

IP_CADDY = "172.28.0.4"
VISITANTE_A = "8.8.8.8"
VISITANTE_B = "1.1.1.1"
DATOS_INCORRECTOS = {"username": "nadie@example.com", "password": "clave-incorrecta"}


def _ip_vista_por_axes(**encabezados):
    pedido = RequestFactory().get("/", REMOTE_ADDR=IP_CADDY, **encabezados)
    return get_client_ip_address(pedido)


def test_usa_la_ip_que_deja_caddy():
    assert _ip_vista_por_axes(HTTP_X_FORWARDED_FOR=VISITANTE_A) == VISITANTE_A


def test_sin_encabezado_usa_la_ip_de_la_conexion():
    assert _ip_vista_por_axes() == IP_CADDY


def test_encabezado_falsificado_no_se_acepta():
    ip = _ip_vista_por_axes(HTTP_X_FORWARDED_FOR=f"{VISITANTE_B}, {VISITANTE_A}")
    assert ip != VISITANTE_B


@pytest.mark.django_db
def test_el_bloqueo_de_una_ip_no_afecta_a_otra(client):
    url = reverse("cuentas:login")
    for _ in range(6):
        client.post(url, DATOS_INCORRECTOS, HTTP_X_FORWARDED_FOR=VISITANTE_A)

    bloqueado = client.post(url, DATOS_INCORRECTOS, HTTP_X_FORWARDED_FOR=VISITANTE_A)
    otra_persona = client.post(url, DATOS_INCORRECTOS, HTTP_X_FORWARDED_FOR=VISITANTE_B)

    assert bloqueado.status_code == 429
    assert otra_persona.status_code == 200
