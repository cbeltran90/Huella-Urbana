from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cuentas import eliminacion
from apps.cuentas.forms import MENSAJE_LOGIN_INVALIDO
from apps.cuentas.models import EstadoCuenta, Sancion, Usuario
from apps.fichas.models import FichaAnimal
from apps.transito import servicios as servicios_transito

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"
CONFIRMAR = "Sí, eliminar mi cuenta"

pytestmark = pytest.mark.django_db


def url():
    return reverse("cuentas:eliminar_cuenta")


@pytest.fixture(autouse=True)
def sin_pasos_de_otros_modulos(monkeypatch):
    monkeypatch.setattr(eliminacion, "_LIMPIEZAS", [])


@pytest.fixture
def ana(client):
    usuario = Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


def sancionar(usuario, tipo, **campos):
    return Sancion.objects.create(
        usuario=usuario,
        email_hash=usuario.email_hash,
        tipo=tipo,
        motivo="Motivo de prueba",
        **campos,
    )


def hay_sesion(client):
    return "_auth_user_id" in client.session


def test_un_visitante_va_al_ingreso(client):
    assert client.get(url()).status_code == 302
    assert client.post(url()).status_code == 302
    assert not Usuario.objects.exists()


def test_la_pantalla_informa_que_se_borra_y_que_se_conserva_y_pide_confirmar(client, ana):
    respuesta = client.get(url())

    contenido = respuesta.content.decode()
    assert respuesta.status_code == 200
    assert "Qué se borra" in contenido
    assert "Qué se conserva, sin tu nombre" in contenido
    assert CONFIRMAR in contenido
    assert f'href="{reverse("cuentas:perfil")}"' in contenido


def test_abrir_la_pantalla_no_cambia_nada(client, ana):
    client.get(url())

    ana.refresh_from_db()
    assert ana.estado_cuenta == EstadoCuenta.ACTIVA
    assert ana.email == "ana@example.com"
    assert hay_sesion(client)


def test_confirmar_elimina_la_cuenta_cierra_la_sesion_y_confirma(client, ana):
    respuesta = client.post(url())

    assert respuesta.status_code == 302
    assert respuesta.url == reverse("cuentas:cuenta_eliminada")
    ana.refresh_from_db()
    assert ana.estado_cuenta == EstadoCuenta.ELIMINADA
    assert not hay_sesion(client)
    assert "Tu cuenta fue eliminada" in client.get(respuesta.url).content.decode()


def test_la_pantalla_de_cuenta_eliminada_es_publica(client):
    assert client.get(reverse("cuentas:cuenta_eliminada")).status_code == 200


def test_la_cuenta_eliminada_ya_no_puede_ingresar(client, ana):
    client.post(url())

    respuesta = client.post(
        reverse("cuentas:login"), {"username": "ana@example.com", "password": CLAVE}
    )

    assert MENSAJE_LOGIN_INVALIDO in respuesta.content.decode()
    assert not hay_sesion(client)


def test_una_suspension_temporal_lo_impide_y_muestra_la_fecha_de_fin(client, ana):
    fin = timezone.now() + timedelta(days=7)
    sancionar(ana, Sancion.Tipo.TEMPORAL, fin=fin)

    respuesta = client.get(url())

    contenido = respuesta.content.decode()
    assert timezone.localtime(fin).strftime("%d/%m/%Y %H:%M") in contenido
    assert CONFIRMAR not in contenido


def test_las_fichas_en_el_circuito_se_listan_y_no_se_puede_confirmar(client, ana):
    FichaAnimal.objects.create(
        nombre="Firulais",
        especie="perro",
        estado=FichaAnimal.Estado.EN_ADOPCION,
        responsable=ana,
    )

    contenido = client.get(url()).content.decode()

    assert "Firulais" in contenido
    assert CONFIRMAR not in contenido


def test_una_eleccion_pendiente_lo_impide(client, ana, monkeypatch):
    monkeypatch.setattr(servicios_transito, "tiene_eleccion_pendiente", lambda usuario: True)

    contenido = client.get(url()).content.decode()

    assert eliminacion.MENSAJE_ELECCION_PENDIENTE in contenido
    assert CONFIRMAR not in contenido


def test_confirmar_con_impedimentos_no_elimina_nada(client, ana):
    sancionar(ana, Sancion.Tipo.TEMPORAL, fin=timezone.now() + timedelta(days=3))

    respuesta = client.post(url())

    assert respuesta.status_code == 200
    assert eliminacion.MENSAJE_SUSPENSION_TEMPORAL in respuesta.content.decode()
    ana.refresh_from_db()
    assert ana.estado_cuenta == EstadoCuenta.ACTIVA
    assert hay_sesion(client)


def test_quien_tiene_una_suspension_permanente_puede_eliminar_su_cuenta(client, ana):
    sancionar(ana, Sancion.Tipo.PERMANENTE)

    respuesta = client.post(url())

    assert respuesta.url == reverse("cuentas:cuenta_eliminada")
    ana.refresh_from_db()
    assert ana.estado_cuenta == EstadoCuenta.ELIMINADA


def test_si_algo_cambia_entre_abrir_y_confirmar_se_informa(client, ana, monkeypatch):
    # La pantalla se abre sin impedimentos, pero al confirmar el servicio encuentra uno.
    impedimento = eliminacion.Impedimento("eleccion_pendiente", "Mensaje de prueba")

    def rechaza(usuario):
        raise eliminacion.EliminacionNoPermitida([impedimento])

    monkeypatch.setattr(eliminacion, "eliminar_cuenta", rechaza)

    respuesta = client.post(url())

    assert respuesta.status_code == 200
    assert "Mensaje de prueba" in respuesta.content.decode()
    ana.refresh_from_db()
    assert ana.estado_cuenta == EstadoCuenta.ACTIVA
