import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse

from apps.cuentas import servicios
from apps.cuentas.forms import MENSAJE_PUNTO_DOMICILIO
from apps.cuentas.models import Domicilio, EstadoCuenta, Rol, Sancion, Usuario

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"
EXACTO = Point(-68.3100, -54.8100, srid=4326)
DESPLAZADO = Point(-68.3040, -54.8025, srid=4326)


def url():
    return reverse("cuentas:domicilio")


@pytest.fixture
def ana(client):
    usuario = Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


def guardar(client, **datos):
    return client.post(url(), datos)


@pytest.mark.django_db
def test_un_visitante_va_al_ingreso(client):
    respuesta = client.get(url())
    assert respuesta.status_code == 302
    assert respuesta.url.startswith("/cuentas/ingresar/?next=/cuentas/domicilio/")


@pytest.mark.django_db
def test_una_cuenta_suspendida_recibe_403_y_no_guarda(client, ana):
    moderadora = Usuario.objects.create_user(
        "mod@example.com", "Mod", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, rol=Rol.MODERADOR
    )
    servicios.sancionar(ana, Sancion.Tipo.PERMANENTE, "Motivo", moderadora)

    respuesta = guardar(client, latitud=EXACTO.y, longitud=EXACTO.x)

    assert respuesta.status_code == 403
    assert not Domicilio.objects.exists()


@pytest.mark.django_db
def test_la_pantalla_carga_con_el_mapa_y_el_radio(client, ana):
    respuesta = client.get(url())
    contenido = respuesta.content.decode()
    assert respuesta.status_code == 200
    assert 'id="mapa-domicilio"' in contenido
    assert "150 metros" in contenido


@pytest.mark.django_db
def test_la_pantalla_tiene_un_enlace_para_volver_al_perfil(client, ana):
    contenido = client.get(url()).content.decode()
    assert reverse("cuentas:perfil") in contenido
    assert "Volver a mi perfil" in contenido


@pytest.mark.django_db
def test_la_pantalla_no_pide_una_direccion_escrita(client, ana):
    assert "direccion" not in client.get(url()).content.decode()


@pytest.mark.django_db
def test_se_guarda_el_domicilio_y_vuelve_al_perfil(client, ana):
    respuesta = guardar(client, latitud=EXACTO.y, longitud=EXACTO.x)

    assert respuesta.status_code == 302
    assert respuesta.url == f"{reverse('cuentas:perfil')}?guardado=1"
    assert Domicilio.objects.get(usuario=ana).ubicacion.equals_exact(EXACTO, 1e-9)
    assert "Guardamos tus cambios" in client.get(respuesta.url).content.decode()


@pytest.mark.django_db
def test_un_punto_fuera_de_ushuaia_se_rechaza(client, ana):
    respuesta = guardar(client, latitud=-34.6037, longitud=-58.3816)
    assert respuesta.status_code == 200
    assert servicios.MENSAJE_FUERA_DE_ZONA in respuesta.content.decode()
    assert not Domicilio.objects.exists()


@pytest.mark.django_db
def test_sin_punto_pide_marcarlo(client, ana):
    respuesta = guardar(client)
    assert respuesta.status_code == 200
    assert MENSAJE_PUNTO_DOMICILIO in respuesta.content.decode()
    assert not Domicilio.objects.exists()


@pytest.mark.django_db
def test_con_una_sola_coordenada_pide_marcarlo(client, ana):
    respuesta = guardar(client, latitud=EXACTO.y)
    assert respuesta.status_code == 200
    assert MENSAJE_PUNTO_DOMICILIO in respuesta.content.decode()


@pytest.mark.django_db
def test_una_coordenada_que_no_es_un_numero_se_rechaza(client, ana):
    respuesta = guardar(client, latitud="abc", longitud="def")
    assert respuesta.status_code == 200
    assert not Domicilio.objects.exists()


@pytest.mark.django_db
def test_guardar_el_mismo_punto_conserva_el_desplazamiento(client, ana):
    antes = servicios.guardar_domicilio(ana, EXACTO)

    respuesta = guardar(client, latitud=EXACTO.y, longitud=EXACTO.x)

    assert respuesta.status_code == 302
    despues = Domicilio.objects.get(usuario=ana)
    assert despues.ubicacion_desplazada.equals_exact(antes.ubicacion_desplazada, 1e-9)


@pytest.mark.django_db
def test_la_pantalla_no_revela_el_punto_exacto(client, ana):
    Domicilio.objects.create(usuario=ana, ubicacion=EXACTO, ubicacion_desplazada=DESPLAZADO)

    contenido = client.get(url()).content.decode()

    assert "-54.8025" in contenido  # el desplazado, que es el que se muestra
    assert "54.8100" not in contenido  # el exacto nunca llega al navegador
    assert "68.3100" not in contenido
