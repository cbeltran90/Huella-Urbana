import re
from urllib.parse import urlparse

import pytest
from django.core.cache import caches
from django.urls import reverse

from apps.cuentas.models import EstadoCuenta, Usuario

CLAVE = "clave-de-prueba-1"


@pytest.fixture(autouse=True)
def limpiar_espera():
    caches["reenvios"].clear()
    yield
    caches["reenvios"].clear()


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def pedir(client, email="ana@example.com"):
    return client.post(reverse("cuentas:recuperar"), {"email": email})


@pytest.mark.django_db
def test_la_pagina_de_pedido_carga(client):
    respuesta = client.get(reverse("cuentas:recuperar"))
    assert respuesta.status_code == 200
    assert 'name="email"' in respuesta.content.decode()


@pytest.mark.django_db
def test_una_cuenta_activa_recibe_el_enlace(client, ana, mailoutbox):
    respuesta = pedir(client)
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("cuentas:recuperar_listo")
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["ana@example.com"]
    assert "contraseña" in mailoutbox[0].subject
    assert "/cuentas/recuperar/" in mailoutbox[0].body


@pytest.mark.django_db
def test_el_enlace_del_correo_abre_el_formulario(client, ana, mailoutbox):
    pedir(client)
    enlace = re.search(r"https?://\S+/cuentas/recuperar/\S+/", mailoutbox[0].body).group()

    respuesta = client.get(urlparse(enlace).path, follow=True)

    assert 'name="new_password1"' in respuesta.content.decode()


@pytest.mark.django_db
def test_el_correo_no_distingue_mayusculas(client, ana, mailoutbox):
    pedir(client, "ANA@Example.com")
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_un_correo_desconocido_responde_igual_y_no_envia(client, mailoutbox):
    respuesta = pedir(client, "nadie@example.com")
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("cuentas:recuperar_listo")
    assert mailoutbox == []


@pytest.mark.django_db
@pytest.mark.parametrize("estado", [EstadoCuenta.PENDIENTE, EstadoCuenta.ELIMINADA])
def test_las_cuentas_no_activas_no_reciben_el_enlace(client, mailoutbox, estado):
    Usuario.objects.create_user("beto@example.com", "Beto", CLAVE, estado_cuenta=estado)
    respuesta = pedir(client, "beto@example.com")
    assert respuesta.url == reverse("cuentas:recuperar_listo")
    assert mailoutbox == []


@pytest.mark.django_db
def test_dos_pedidos_seguidos_envian_un_solo_correo(client, ana, mailoutbox):
    primero = pedir(client)
    segundo = pedir(client)
    assert primero.url == segundo.url == reverse("cuentas:recuperar_listo")
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_un_fallo_de_envio_no_rompe_la_pantalla(client, ana, monkeypatch):
    def fallar(self, *args, **kwargs):
        raise OSError("sin red")

    monkeypatch.setattr("django.core.mail.EmailMultiAlternatives.send", fallar)
    respuesta = pedir(client)
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("cuentas:recuperar_listo")


@pytest.mark.django_db
def test_la_pagina_de_aviso_carga(client):
    respuesta = client.get(reverse("cuentas:recuperar_listo"))
    assert respuesta.status_code == 200
    assert "Revisá tu correo" in respuesta.content.decode()


@pytest.mark.django_db
def test_un_enlace_muerto_ofrece_pedir_otro(client):
    url = reverse("cuentas:recuperar_confirmar", args=["MQ", "token-falso"])
    respuesta = client.get(url, follow=True)
    assert reverse("cuentas:recuperar") in respuesta.content.decode()
