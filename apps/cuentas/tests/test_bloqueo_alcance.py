"""El bloqueo de ingreso afecta solo a la combinación correo + IP (CU-02)."""

import pytest
from django.urls import reverse

IP_A = "8.8.8.8"
IP_B = "1.1.1.1"


def _fallar(client, correo, ip, veces=5):
    url = reverse("cuentas:login")
    datos = {"username": correo, "password": "clave-incorrecta"}
    respuesta = None
    for _ in range(veces):
        respuesta = client.post(url, datos, HTTP_X_FORWARDED_FOR=ip)
    return respuesta


@pytest.mark.django_db
def test_otro_correo_desde_la_misma_ip_no_queda_bloqueado(client):
    assert _fallar(client, "ana@example.com", IP_A).status_code == 429

    respuesta = _fallar(client, "luis@example.com", IP_A, veces=1)

    assert respuesta.status_code == 200


@pytest.mark.django_db
def test_el_mismo_correo_desde_otra_ip_no_queda_bloqueado(client):
    assert _fallar(client, "ana@example.com", IP_A).status_code == 429

    respuesta = _fallar(client, "ana@example.com", IP_B, veces=1)

    assert respuesta.status_code == 200


@pytest.mark.django_db
def test_mayusculas_y_espacios_cuentan_como_el_mismo_correo(client):
    variantes = ["ana@example.com", "ANA@Example.com", " ana@example.com ", "Ana@example.com"]
    for correo in variantes:
        _fallar(client, correo, IP_A, veces=1)

    respuesta = _fallar(client, "ANA@EXAMPLE.COM", IP_A, veces=1)

    assert respuesta.status_code == 429
