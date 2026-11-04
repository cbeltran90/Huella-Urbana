import pytest
from constance import config
from constance import settings as ajustes
from constance.admin import Config
from constance.forms import ConstanceForm
from constance.utils import get_values
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.cuentas.models import EstadoCuenta, Rol, Usuario

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"
PARAMETROS = "admin:constance_config_changelist"
HISTORIAL = "admin:constance_config_history"


@pytest.fixture(autouse=True)
def limpiar_tipos_de_contenido():
    """Constance crea el tipo de contenido de «Config» al registrar un cambio.

    La base se revierte al terminar cada test, pero la caché de Django seguiría apuntando
    a una fila que ya no existe: se vacía antes y después de cada test.
    """
    ContentType.objects.clear_cache()
    yield
    ContentType.objects.clear_cache()


@pytest.fixture
def administrador(client):
    usuario = Usuario.objects.create_user(
        "admin@example.com",
        "Admin",
        CLAVE,
        rol=Rol.ADMINISTRADOR,
        estado_cuenta=EstadoCuenta.ACTIVA,
    )
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


def confirmar(client, **cambios):
    """Envía la pantalla de parámetros con los valores actuales y los cambios pedidos."""
    actuales = get_values()
    datos = {nombre: actuales[nombre] for nombre in ajustes.CONFIG}
    datos.update(cambios)
    datos["version"] = ConstanceForm(initial=actuales).initial["version"]
    return client.post(reverse(PARAMETROS), datos)


def registros():
    return LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(Config), object_id="Config"
    )


@pytest.mark.django_db
def test_un_cambio_valido_se_guarda_y_se_aplica(client, administrador):
    respuesta = confirmar(client, RADIO_DOMICILIO_METROS=300)

    assert respuesta.status_code == 302
    assert config.RADIO_DOMICILIO_METROS == 300


@pytest.mark.django_db
def test_se_pueden_cambiar_varios_valores_a_la_vez(client, administrador):
    respuesta = confirmar(client, DIAS_PRIMERA_SUSPENSION=14, UMBRAL_SIMILITUD=0.9)

    assert respuesta.status_code == 302
    assert config.DIAS_PRIMERA_SUSPENSION == 14
    assert config.UMBRAL_SIMILITUD == 0.9


@pytest.mark.django_db
def test_un_valor_invalido_se_rechaza_y_no_cambia_nada(client, administrador):
    respuesta = confirmar(client, RADIO_DOMICILIO_METROS=0)

    assert respuesta.status_code == 200
    assert config.RADIO_DOMICILIO_METROS == 150
    assert not registros().exists()


@pytest.mark.django_db
def test_si_un_valor_es_invalido_no_se_guarda_ninguno(client, administrador):
    respuesta = confirmar(client, DIAS_PRIMERA_SUSPENSION=14, RADIO_DOMICILIO_METROS=0)

    assert respuesta.status_code == 200
    assert config.DIAS_PRIMERA_SUSPENSION == 7
    assert config.RADIO_DOMICILIO_METROS == 150


@pytest.mark.django_db
def test_el_cambio_queda_registrado_con_quien_cuando_y_que(client, administrador):
    confirmar(client, RADIO_DOMICILIO_METROS=300, DIAS_PRIMERA_SUSPENSION=14)

    entrada = registros().get()
    assert entrada.user == administrador
    assert entrada.action_flag == CHANGE
    assert entrada.action_time is not None
    mensaje = entrada.get_change_message()
    assert "RADIO_DOMICILIO_METROS" in mensaje
    assert "DIAS_PRIMERA_SUSPENSION" in mensaje
    assert "UMBRAL_PHASH" not in mensaje


@pytest.mark.django_db
def test_confirmar_sin_cambios_no_deja_registro(client, administrador):
    respuesta = confirmar(client)

    assert respuesta.status_code == 302
    assert not registros().exists()


@pytest.mark.django_db
def test_el_administrador_ve_el_historial(client, administrador):
    confirmar(client, RADIO_DOMICILIO_METROS=300)

    respuesta = client.get(reverse(HISTORIAL))

    assert respuesta.status_code == 200
    assert "RADIO_DOMICILIO_METROS" in respuesta.content.decode()


@pytest.mark.django_db
def test_el_moderador_no_ve_el_historial(client):
    moderador = Usuario.objects.create_user(
        "mod@example.com", "Moderadora", CLAVE, rol=Rol.MODERADOR, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(moderador, backend=BACKEND_MODELO)

    assert client.get(reverse(HISTORIAL)).status_code == 403
