from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.forms import MENSAJE_CUENTA_SUSPENDIDA, MENSAJE_LOGIN_INVALIDO
from apps.cuentas.models import EstadoCuenta, Sancion, Usuario

CLAVE = "clave-de-prueba-1"
MOTIVO = "Motivo de prueba"

pytestmark = pytest.mark.django_db


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def sancionar(usuario, tipo, **campos):
    return Sancion.objects.create(
        usuario=usuario, email_hash=usuario.email_hash, tipo=tipo, motivo=MOTIVO, **campos
    )


def entrar(client, clave=CLAVE):
    return client.post(reverse("cuentas:login"), {"username": "ana@example.com", "password": clave})


def hay_sesion(client):
    return "_auth_user_id" in client.session


def test_una_suspension_temporal_no_deja_entrar_y_muestra_motivo_y_fecha_de_fin(client, ana):
    fin = timezone.now() + timedelta(days=7)
    sancionar(ana, Sancion.Tipo.TEMPORAL, fin=fin)

    respuesta = entrar(client)

    assert respuesta.status_code == 200
    assert not hay_sesion(client)
    contenido = respuesta.content.decode()
    assert MENSAJE_CUENTA_SUSPENDIDA in contenido
    assert MOTIVO in contenido
    assert timezone.localtime(fin).strftime("%d/%m/%Y %H:%M") in contenido


def test_una_suspension_permanente_no_deja_entrar_y_muestra_el_motivo(client, ana):
    sancionar(ana, Sancion.Tipo.PERMANENTE)

    respuesta = entrar(client)

    assert respuesta.status_code == 200
    assert not hay_sesion(client)
    contenido = respuesta.content.decode()
    assert MOTIVO in contenido
    assert "La suspensión es permanente" in contenido


def test_con_la_clave_incorrecta_no_se_revela_la_suspension(client, ana):
    sancionar(ana, Sancion.Tipo.PERMANENTE)

    respuesta = entrar(client, clave="otra-clave-incorrecta")

    contenido = respuesta.content.decode()
    assert MENSAJE_LOGIN_INVALIDO in contenido
    assert MENSAJE_CUENTA_SUSPENDIDA not in contenido
    assert MOTIVO not in contenido


def test_una_suspension_vencida_deja_entrar(client, ana):
    sancionar(
        ana,
        Sancion.Tipo.TEMPORAL,
        inicio=timezone.now() - timedelta(days=8),
        fin=timezone.now() - timedelta(days=1),
    )

    assert entrar(client).status_code == 302
    assert hay_sesion(client)


def test_una_suspension_levantada_deja_entrar(client, ana):
    sancionar(ana, Sancion.Tipo.PERMANENTE, revocada_en=timezone.now())

    assert entrar(client).status_code == 302
    assert hay_sesion(client)


def test_la_suspension_de_otra_cuenta_no_afecta(client, ana):
    otra = Usuario.objects.create_user(
        "otra@example.com", "Otra", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    sancionar(otra, Sancion.Tipo.PERMANENTE)

    assert entrar(client).status_code == 302


def test_la_suspension_permanente_ofrece_eliminar_la_cuenta(client, ana):
    sancionar(ana, Sancion.Tipo.PERMANENTE)

    contenido = entrar(client).content.decode()

    assert f'href="{reverse("cuentas:eliminar_cuenta_suspendida")}"' in contenido
    assert "Eliminar mi cuenta" in contenido


def test_la_suspension_temporal_no_ofrece_eliminar_la_cuenta(client, ana):
    sancionar(ana, Sancion.Tipo.TEMPORAL, fin=timezone.now() + timedelta(days=7))

    contenido = entrar(client).content.decode()

    assert "Eliminar mi cuenta" not in contenido
