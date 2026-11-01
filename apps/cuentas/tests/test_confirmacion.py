import re
from urllib.parse import urlparse

import pytest
from django.urls import reverse

from apps.cuentas import servicios
from apps.cuentas.models import EstadoCuenta, Usuario

CLAVE = "clave-de-prueba-1"


def datos(**cambios):
    base = {
        "nombre_usuario": "Ana",
        "email": "ana@example.com",
        "password1": CLAVE,
        "password2": CLAVE,
        "acepta_condiciones": "on",
    }
    return {**base, **cambios}


def registrar_y_obtener_la_ruta_del_enlace(client, mailoutbox):
    client.post(reverse("cuentas:registro"), datos())
    enlace = re.search(r"http://testserver\S+", mailoutbox[0].body).group(0)
    return urlparse(enlace).path


@pytest.mark.django_db
def test_el_registro_envia_un_correo_con_el_enlace(client, mailoutbox):
    client.post(reverse("cuentas:registro"), datos())
    assert len(mailoutbox) == 1
    correo = mailoutbox[0]
    assert correo.to == ["ana@example.com"]
    assert "Confirmá tu cuenta" in correo.subject
    assert "/cuentas/confirmar/" in correo.body


@pytest.mark.django_db
def test_el_enlace_activa_la_cuenta(client, mailoutbox):
    ruta = registrar_y_obtener_la_ruta_del_enlace(client, mailoutbox)
    respuesta = client.get(ruta)
    assert respuesta.status_code == 200
    assert "Cuenta activada" in respuesta.content.decode()
    usuario = Usuario.objects.get(email="ana@example.com")
    assert usuario.estado_cuenta == EstadoCuenta.ACTIVA
    assert usuario.is_active


@pytest.mark.django_db
def test_abrir_el_enlace_dos_veces_no_da_error(client, mailoutbox):
    ruta = registrar_y_obtener_la_ruta_del_enlace(client, mailoutbox)
    client.get(ruta)
    assert client.get(ruta).status_code == 200


@pytest.mark.django_db
def test_un_enlace_alterado_no_activa_nada(client, mailoutbox):
    registrar_y_obtener_la_ruta_del_enlace(client, mailoutbox)
    respuesta = client.get("/cuentas/confirmar/token-falso/")
    assert respuesta.status_code == 400
    assert "El enlace no es válido" in respuesta.content.decode()
    usuario = Usuario.objects.get(email="ana@example.com")
    assert usuario.estado_cuenta == EstadoCuenta.PENDIENTE


@pytest.mark.django_db
def test_un_enlace_vencido_no_activa_la_cuenta(client, mailoutbox, monkeypatch):
    ruta = registrar_y_obtener_la_ruta_del_enlace(client, mailoutbox)
    monkeypatch.setattr(servicios, "DIAS_VIGENCIA_ENLACE", -1)
    assert client.get(ruta).status_code == 400
    usuario = Usuario.objects.get(email="ana@example.com")
    assert usuario.estado_cuenta == EstadoCuenta.PENDIENTE


@pytest.mark.django_db
def test_el_enlace_de_una_cuenta_eliminada_no_la_reactiva(client):
    usuario = Usuario.objects.create_user(
        "x@example.com", "Equis", CLAVE, estado_cuenta=EstadoCuenta.ELIMINADA
    )
    ruta = reverse("cuentas:confirmar", args=[servicios.crear_token_confirmacion(usuario)])
    assert client.get(ruta).status_code == 400
    usuario.refresh_from_db()
    assert usuario.estado_cuenta == EstadoCuenta.ELIMINADA


@pytest.mark.django_db
def test_si_falla_el_envio_la_cuenta_se_crea_igual(client, monkeypatch):
    def falla(*args, **kwargs):
        raise OSError

    monkeypatch.setattr(servicios, "send_mail", falla)
    respuesta = client.post(reverse("cuentas:registro"), datos())
    assert respuesta.status_code == 302
    assert Usuario.objects.filter(email="ana@example.com").exists()


@pytest.mark.django_db
def test_el_token_identifica_al_usuario():
    usuario = Usuario.objects.create_user("ana@example.com", "Ana", CLAVE)
    token = servicios.crear_token_confirmacion(usuario)
    assert servicios.usuario_de_token(token) == usuario
    assert servicios.usuario_de_token(token + "x") is None
    assert servicios.usuario_de_token("basura") is None
