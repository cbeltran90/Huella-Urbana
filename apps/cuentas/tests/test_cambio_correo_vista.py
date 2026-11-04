import re

import pytest
from django.core.cache import caches
from django.test import Client
from django.urls import reverse

from apps.cuentas import servicios
from apps.cuentas.models import EstadoCuenta, Rol, Sancion, Usuario
from apps.cuentas.views import MENSAJE_ENVIO_FALLIDO

CLAVE = "clave-de-prueba-1"
NUEVO = "nuevo@example.com"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"


def url():
    return reverse("cuentas:cambiar_correo")


@pytest.fixture(autouse=True)
def sin_esperas():
    caches["reenvios"].clear()
    yield
    caches["reenvios"].clear()


@pytest.fixture
def ana(client):
    usuario = Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


def pedir(client, correo=NUEVO):
    return client.post(url(), {"email": correo})


@pytest.mark.django_db
@pytest.mark.parametrize("nombre", ["cuentas:cambiar_correo", "cuentas:cambiar_correo_enviado"])
def test_un_visitante_va_al_ingreso(client, nombre):
    respuesta = client.get(reverse(nombre))
    assert respuesta.status_code == 302
    assert respuesta.url.startswith("/cuentas/ingresar/?next=")


@pytest.mark.django_db
def test_una_cuenta_suspendida_recibe_403_y_no_se_envia_nada(client, ana, mailoutbox):
    moderadora = Usuario.objects.create_user(
        "mod@example.com", "Mod", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, rol=Rol.MODERADOR
    )
    servicios.sancionar(ana, Sancion.Tipo.PERMANENTE, "Motivo", moderadora)

    assert client.get(url()).status_code == 403
    assert pedir(client).status_code == 403
    assert client.get(reverse("cuentas:cambiar_correo_enviado")).status_code == 403
    assert mailoutbox == []


@pytest.mark.django_db
def test_la_pantalla_muestra_el_correo_actual_y_el_campo(client, ana):
    contenido = client.get(url()).content.decode()
    assert "ana@example.com" in contenido
    assert 'name="email"' in contenido


@pytest.mark.django_db
def test_se_envia_el_enlace_y_el_correo_actual_no_cambia(client, ana, mailoutbox):
    respuesta = pedir(client)

    assert respuesta.status_code == 302
    assert respuesta.url == reverse("cuentas:cambiar_correo_enviado")
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == [NUEVO]
    ana.refresh_from_db()
    assert ana.email == "ana@example.com"
    assert "Revisá tu correo nuevo" in client.get(respuesta.url).content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("correo", ["", "no-es-un-correo"])
def test_un_correo_vacio_o_mal_escrito_se_rechaza(client, ana, mailoutbox, correo):
    assert pedir(client, correo).status_code == 200
    assert mailoutbox == []


@pytest.mark.django_db
def test_el_mismo_correo_de_la_cuenta_se_rechaza(client, ana, mailoutbox):
    respuesta = pedir(client, "ana@example.com")
    assert respuesta.status_code == 200
    assert servicios.MENSAJE_CORREO_IGUAL in respuesta.content.decode()
    assert mailoutbox == []


@pytest.mark.django_db
def test_un_correo_de_otra_cuenta_se_rechaza(client, ana, mailoutbox):
    Usuario.objects.create_user(
        "beto@example.com", "Beto", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    respuesta = pedir(client, "beto@example.com")
    assert respuesta.status_code == 200
    assert servicios.MENSAJE_CORREO_USADO in respuesta.content.decode()
    assert mailoutbox == []


@pytest.mark.django_db
def test_no_se_puede_pedir_otro_enlace_enseguida(client, ana, mailoutbox):
    pedir(client)
    respuesta = pedir(client, "otro@example.com")
    assert respuesta.status_code == 200
    assert servicios.MENSAJE_CAMBIO_RECIENTE in respuesta.content.decode()
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_si_falla_el_envio_se_avisa_y_se_puede_reintentar(client, ana, mailoutbox, monkeypatch):
    def falla(*args, **kwargs):
        raise OSError("sin conexión")

    monkeypatch.setattr(servicios, "send_mail", falla)
    respuesta = pedir(client)
    assert respuesta.status_code == 200
    assert MENSAJE_ENVIO_FALLIDO in respuesta.content.decode()

    monkeypatch.undo()
    assert pedir(client).status_code == 302
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_el_cambio_completo_de_punta_a_punta(client, ana, mailoutbox):
    pedir(client)
    ruta = re.search(r"/cuentas/correo/confirmar/[^/\s]+/", mailoutbox[0].body).group(0)

    # El enlace se abre desde otro navegador, sin sesión.
    assert Client().get(ruta).status_code == 200

    ana.refresh_from_db()
    assert ana.email == NUEVO
    ingreso = Client().post(reverse("cuentas:login"), {"username": NUEVO, "password": CLAVE})
    assert ingreso.status_code == 302
    viejo = Client().post(
        reverse("cuentas:login"), {"username": "ana@example.com", "password": CLAVE}
    )
    assert viejo.status_code == 200
