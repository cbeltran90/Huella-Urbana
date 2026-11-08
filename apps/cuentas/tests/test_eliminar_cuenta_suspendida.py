import time
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cuentas import eliminacion
from apps.cuentas.models import EstadoCuenta, Sancion, Usuario
from apps.cuentas.views import CLAVE_SESION_ELIMINACION
from apps.fichas.models import FichaAnimal

CLAVE = "clave-de-prueba-1"
CONFIRMAR = "Sí, eliminar mi cuenta"

pytestmark = pytest.mark.django_db


def url():
    return reverse("cuentas:eliminar_cuenta_suspendida")


@pytest.fixture(autouse=True)
def sin_pasos_de_otros_modulos(monkeypatch):
    monkeypatch.setattr(eliminacion, "_LIMPIEZAS", [])


@pytest.fixture
def ana():
    usuario = Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    Sancion.objects.create(
        usuario=usuario,
        email_hash=usuario.email_hash,
        tipo=Sancion.Tipo.PERMANENTE,
        motivo="Motivo de prueba",
    )
    return usuario


def recordar(client, usuario, segundos=600):
    """Deja la cuenta recordada en la sesión, como hace el ingreso."""
    sesion = client.session
    sesion[CLAVE_SESION_ELIMINACION] = {"usuario": usuario.pk, "hasta": time.time() + segundos}
    sesion.save()


def test_sin_cuenta_recordada_vuelve_al_ingreso(client, ana):
    assert client.get(url()).url == reverse("cuentas:login")
    assert client.post(url()).url == reverse("cuentas:login")
    ana.refresh_from_db()
    assert ana.estado_cuenta == EstadoCuenta.ACTIVA


def test_una_cuenta_recordada_hace_demasiado_tiempo_ya_no_sirve(client, ana):
    recordar(client, ana, segundos=-1)

    respuesta = client.post(url())

    assert respuesta.url == reverse("cuentas:login")
    assert CLAVE_SESION_ELIMINACION not in client.session
    ana.refresh_from_db()
    assert ana.estado_cuenta == EstadoCuenta.ACTIVA


def test_si_la_suspension_ya_no_es_permanente_no_sirve(client, ana):
    recordar(client, ana)
    Sancion.objects.filter(usuario=ana).update(revocada_en=timezone.now())

    assert client.get(url()).url == reverse("cuentas:login")


def test_si_ahora_la_suspension_es_temporal_no_sirve(client, ana):
    recordar(client, ana)
    Sancion.objects.filter(usuario=ana).delete()
    Sancion.objects.create(
        usuario=ana,
        email_hash=ana.email_hash,
        tipo=Sancion.Tipo.TEMPORAL,
        motivo="Motivo de prueba",
        fin=timezone.now() + timedelta(days=7),
    )

    assert client.post(url()).url == reverse("cuentas:login")
    ana.refresh_from_db()
    assert ana.estado_cuenta == EstadoCuenta.ACTIVA


def test_una_cuenta_ya_eliminada_no_sirve(client, ana):
    recordar(client, ana)
    eliminacion.eliminar_cuenta(ana)

    assert client.get(url()).url == reverse("cuentas:login")


def test_la_pantalla_informa_y_pide_confirmar_sin_abrir_una_sesion(client, ana):
    recordar(client, ana)

    respuesta = client.get(url())

    contenido = respuesta.content.decode()
    assert respuesta.status_code == 200
    assert "Qué se borra" in contenido
    assert CONFIRMAR in contenido
    assert f'href="{reverse("cuentas:login")}"' in contenido
    assert "_auth_user_id" not in client.session
    ana.refresh_from_db()
    assert ana.estado_cuenta == EstadoCuenta.ACTIVA


def test_confirmar_elimina_la_cuenta_y_olvida_lo_recordado(client, ana):
    recordar(client, ana)

    respuesta = client.post(url())

    assert respuesta.url == reverse("cuentas:cuenta_eliminada")
    ana.refresh_from_db()
    assert ana.estado_cuenta == EstadoCuenta.ELIMINADA
    assert CLAVE_SESION_ELIMINACION not in client.session
    assert "Tu cuenta fue eliminada" in client.get(respuesta.url).content.decode()


def test_con_impedimentos_no_se_elimina_y_se_listan(client, ana):
    recordar(client, ana)
    FichaAnimal.objects.create(
        nombre="Firulais",
        especie="perro",
        estado=FichaAnimal.Estado.EN_ADOPCION,
        responsable=ana,
    )

    respuesta = client.post(url())

    contenido = respuesta.content.decode()
    assert respuesta.status_code == 200
    assert "Firulais" in contenido
    assert CONFIRMAR not in contenido
    assert "Volver al ingreso" in contenido
    ana.refresh_from_db()
    assert ana.estado_cuenta == EstadoCuenta.ACTIVA


def test_recorrido_completo_desde_el_ingreso(client, ana):
    entrada = client.post(
        reverse("cuentas:login"), {"username": "ana@example.com", "password": CLAVE}
    )
    assert entrada.status_code == 200
    assert "_auth_user_id" not in client.session
    # No tiene ningún permiso: las pantallas con sesión la mandan al ingreso.
    assert client.get(reverse("cuentas:perfil")).status_code == 302

    respuesta = client.post(url())

    assert respuesta.url == reverse("cuentas:cuenta_eliminada")
    ana.refresh_from_db()
    assert ana.estado_cuenta == EstadoCuenta.ELIMINADA
