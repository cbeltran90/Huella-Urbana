import pytest
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.cuentas.forms import MENSAJE_CLAVES_DISTINTAS
from apps.cuentas.models import EstadoCuenta, Usuario

CLAVE_VIEJA = "clave-vieja-12345"
CLAVE_NUEVA = "Zq7mWp3xKdn"
TEXTO_ENLACE_MUERTO = "Este enlace ya no sirve"


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE_VIEJA, estado_cuenta=EstadoCuenta.ACTIVA
    )


def enlace(usuario):
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    return reverse("cuentas:recuperar_confirmar", args=[uid, token])


def abrir(client, url):
    """Abre el enlace como lo hace un navegador. Devuelve la respuesta y la URL final."""
    respuesta = client.get(url, follow=True)
    final = respuesta.redirect_chain[-1][0] if respuesta.redirect_chain else url
    return respuesta, final


def cambiar(client, url, clave1, clave2):
    return client.post(url, {"new_password1": clave1, "new_password2": clave2})


@pytest.mark.django_db
def test_el_plazo_del_enlace_es_de_un_dia(settings):
    assert settings.PASSWORD_RESET_TIMEOUT == 24 * 60 * 60


@pytest.mark.django_db
def test_un_enlace_valido_muestra_el_formulario(client, ana):
    respuesta, _ = abrir(client, enlace(ana))
    assert respuesta.status_code == 200
    assert 'name="new_password1"' in respuesta.content.decode()


@pytest.mark.django_db
def test_se_cambia_la_contrasena_y_no_inicia_sesion(client, ana):
    _, url = abrir(client, enlace(ana))
    respuesta = cambiar(client, url, CLAVE_NUEVA, CLAVE_NUEVA)
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("cuentas:recuperar_completo")
    ana.refresh_from_db()
    assert ana.check_password(CLAVE_NUEVA)
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_una_clave_corta_se_rechaza(client, ana):
    _, url = abrir(client, enlace(ana))
    respuesta = cambiar(client, url, "corta123", "corta123")
    assert respuesta.status_code == 200
    assert "10 caracteres" in respuesta.content.decode()
    ana.refresh_from_db()
    assert ana.check_password(CLAVE_VIEJA)


@pytest.mark.django_db
def test_claves_distintas_se_rechazan(client, ana):
    _, url = abrir(client, enlace(ana))
    respuesta = cambiar(client, url, CLAVE_NUEVA, "otra-clave-distinta-1")
    assert respuesta.status_code == 200
    assert MENSAJE_CLAVES_DISTINTAS in respuesta.content.decode()
    ana.refresh_from_db()
    assert ana.check_password(CLAVE_VIEJA)


@pytest.mark.django_db
def test_el_enlace_no_sirve_dos_veces(client, ana):
    url_enlace = enlace(ana)
    _, url = abrir(client, url_enlace)
    cambiar(client, url, CLAVE_NUEVA, CLAVE_NUEVA)

    respuesta, _ = abrir(client, url_enlace)

    assert TEXTO_ENLACE_MUERTO in respuesta.content.decode()


@pytest.mark.django_db
def test_un_enlace_alterado_no_sirve(client, ana):
    uid = urlsafe_base64_encode(force_bytes(ana.pk))
    url = reverse("cuentas:recuperar_confirmar", args=[uid, "token-falso"])
    respuesta, _ = abrir(client, url)
    assert TEXTO_ENLACE_MUERTO in respuesta.content.decode()


@pytest.mark.django_db
def test_un_enlace_vencido_no_sirve(client, ana, settings):
    settings.PASSWORD_RESET_TIMEOUT = -1
    respuesta, _ = abrir(client, enlace(ana))
    assert TEXTO_ENLACE_MUERTO in respuesta.content.decode()


@pytest.mark.django_db
def test_la_pagina_de_contrasena_cambiada_lleva_al_ingreso(client):
    respuesta = client.get(reverse("cuentas:recuperar_completo"))
    assert respuesta.status_code == 200
    assert reverse("cuentas:login") in respuesta.content.decode()
