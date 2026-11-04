import pytest
from constance import config
from django.urls import reverse

from apps.cuentas.models import EstadoCuenta, Rol, Usuario

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"
PARAMETROS = "admin:constance_config_changelist"


def entrar(client, rol):
    usuario = Usuario.objects.create_user(
        f"{rol}@example.com", rol, CLAVE, rol=rol, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


@pytest.mark.django_db
def test_el_administrador_abre_los_parametros(client):
    entrar(client, Rol.ADMINISTRADOR)

    respuesta = client.get(reverse(PARAMETROS))

    assert respuesta.status_code == 200
    contenido = respuesta.content.decode()
    assert "RADIO_DOMICILIO_METROS" in contenido
    assert "DIAS_PRIMERA_SUSPENSION" in contenido


@pytest.mark.django_db
def test_el_administrador_ve_los_parametros_en_el_menu(client):
    entrar(client, Rol.ADMINISTRADOR)

    respuesta = client.get(reverse("admin:index"))

    assert reverse(PARAMETROS) in respuesta.content.decode()


@pytest.mark.django_db
def test_el_moderador_no_tiene_acceso_a_los_parametros(client):
    entrar(client, Rol.MODERADOR)

    assert client.get(reverse(PARAMETROS)).status_code == 403


@pytest.mark.django_db
def test_el_moderador_no_ve_los_parametros_en_el_menu(client):
    entrar(client, Rol.MODERADOR)

    respuesta = client.get(reverse("admin:index"))

    assert reverse(PARAMETROS) not in respuesta.content.decode()


@pytest.mark.django_db
def test_el_moderador_no_puede_cambiar_un_parametro(client):
    entrar(client, Rol.MODERADOR)
    antes = config.RADIO_DOMICILIO_METROS

    respuesta = client.post(reverse(PARAMETROS), {"RADIO_DOMICILIO_METROS": 999})

    assert respuesta.status_code == 403
    assert config.RADIO_DOMICILIO_METROS == antes


@pytest.mark.django_db
def test_un_registrado_no_entra_a_los_parametros(client):
    entrar(client, Rol.REGISTRADO)

    respuesta = client.get(reverse(PARAMETROS))

    assert respuesta.status_code == 302
    assert "login" in respuesta["Location"]


@pytest.mark.django_db
def test_sin_sesion_no_se_ven_los_parametros(client):
    respuesta = client.get(reverse(PARAMETROS))

    assert respuesta.status_code == 302
    assert "login" in respuesta["Location"]
