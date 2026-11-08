import time
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import EstadoCuenta, Sancion, Usuario
from apps.cuentas.views import CLAVE_SESION_ELIMINACION, MINUTOS_PARA_ELIMINAR_SUSPENDIDA

CLAVE = "clave-de-prueba-1"

pytestmark = pytest.mark.django_db


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def sancionar(usuario, tipo, **campos):
    return Sancion.objects.create(
        usuario=usuario,
        email_hash=usuario.email_hash,
        tipo=tipo,
        motivo="Motivo de prueba",
        **campos,
    )


def entrar(client, clave=CLAVE):
    return client.post(reverse("cuentas:login"), {"username": "ana@example.com", "password": clave})


def test_con_suspension_permanente_se_recuerda_la_cuenta_sin_abrir_la_sesion(client, ana):
    sancionar(ana, Sancion.Tipo.PERMANENTE)

    entrar(client)

    recordada = client.session[CLAVE_SESION_ELIMINACION]
    assert recordada["usuario"] == ana.pk
    margen = MINUTOS_PARA_ELIMINAR_SUSPENDIDA * 60
    assert 0 < recordada["hasta"] - time.time() <= margen
    assert "_auth_user_id" not in client.session


def test_con_suspension_temporal_no_se_recuerda_la_cuenta(client, ana):
    sancionar(ana, Sancion.Tipo.TEMPORAL, fin=timezone.now() + timedelta(days=7))

    entrar(client)

    assert CLAVE_SESION_ELIMINACION not in client.session


def test_con_la_clave_incorrecta_no_se_recuerda_la_cuenta(client, ana):
    sancionar(ana, Sancion.Tipo.PERMANENTE)

    entrar(client, clave="otra-clave-incorrecta")

    assert CLAVE_SESION_ELIMINACION not in client.session


def test_al_ingresar_con_normalidad_se_olvida_la_cuenta_recordada(client, ana):
    sesion = client.session
    sesion[CLAVE_SESION_ELIMINACION] = {"usuario": 999, "hasta": time.time() + 60}
    sesion.save()

    respuesta = entrar(client)

    assert respuesta.status_code == 302
    assert CLAVE_SESION_ELIMINACION not in client.session
