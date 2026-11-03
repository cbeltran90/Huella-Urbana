from datetime import timedelta

import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from apps.cuentas.decoradores import cuenta_habilitada
from apps.cuentas.models import EstadoCuenta, Sancion, Usuario

CLAVE = "clave-de-prueba-1"
LLAMADAS = []


@cuenta_habilitada
def vista_de_prueba(request):
    LLAMADAS.append(request.user)
    return HttpResponse("ok")


@pytest.fixture(autouse=True)
def limpiar_llamadas():
    LLAMADAS.clear()


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def abrir(usuario):
    pedido = RequestFactory().get("/prueba/")
    pedido.user = usuario
    return vista_de_prueba(pedido)


def sancion(usuario, tipo, **campos):
    return Sancion.objects.create(
        usuario=usuario,
        email_hash=usuario.email_hash,
        tipo=tipo,
        motivo="Motivo de prueba",
        **campos,
    )


def test_conserva_el_nombre_de_la_vista():
    assert vista_de_prueba.__name__ == "vista_de_prueba"


def test_un_visitante_va_al_ingreso():
    respuesta = abrir(AnonymousUser())
    assert respuesta.status_code == 302
    assert respuesta.url.startswith("/cuentas/ingresar/?next=/prueba/")
    assert LLAMADAS == []


@pytest.mark.django_db
def test_una_cuenta_sin_sancion_pasa(ana):
    respuesta = abrir(ana)
    assert respuesta.status_code == 200
    assert LLAMADAS == [ana]


@pytest.mark.django_db
def test_una_suspension_temporal_responde_403_con_la_fecha_de_fin(ana):
    fin = timezone.now() + timedelta(days=7)
    sancion(ana, Sancion.Tipo.TEMPORAL, fin=fin)

    respuesta = abrir(ana)

    assert respuesta.status_code == 403
    contenido = respuesta.content.decode()
    assert "Tu cuenta está suspendida" in contenido
    assert timezone.localtime(fin).strftime("%d/%m/%Y %H:%M") in contenido
    assert LLAMADAS == []


@pytest.mark.django_db
def test_una_suspension_permanente_lo_avisa(ana):
    sancion(ana, Sancion.Tipo.PERMANENTE)
    respuesta = abrir(ana)
    assert respuesta.status_code == 403
    assert "permanente" in respuesta.content.decode()


@pytest.mark.django_db
def test_una_suspension_vencida_ya_no_bloquea(ana):
    sancion(
        ana,
        Sancion.Tipo.TEMPORAL,
        inicio=timezone.now() - timedelta(days=8),
        fin=timezone.now() - timedelta(days=1),
    )
    assert abrir(ana).status_code == 200


@pytest.mark.django_db
def test_una_suspension_levantada_ya_no_bloquea(ana):
    sancion(ana, Sancion.Tipo.PERMANENTE, revocada_en=timezone.now())
    assert abrir(ana).status_code == 200
