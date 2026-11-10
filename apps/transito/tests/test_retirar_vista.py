from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import EstadoCuenta, Sancion, Usuario
from apps.fichas.models import FichaAnimal
from apps.transito import postulaciones
from apps.transito.models import PerfilTransito, Postulacion

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"
Estado = Postulacion.Estado

pytestmark = pytest.mark.django_db


def crear_hogar(nombre):
    usuario = Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    PerfilTransito.objects.create(
        usuario=usuario,
        especies_aceptadas="perro",
        tamano_maximo="mediano",
        duracion_maxima_dias=30,
        cupo_declarado=2,
    )
    return usuario


def crear_ficha():
    return FichaAnimal.objects.create(
        nombre="Bruno",
        especie="perro",
        tamano="mediano",
        estado=FichaAnimal.Estado.EN_ADOPCION,
        es_privada=False,
    )


def url(postulacion):
    return reverse("transito:retirar_postulacion", args=[postulacion.pk])


def ficha_url(ficha):
    return reverse("fichas:detalle", args=[ficha.pk])


@pytest.fixture
def lucia(client):
    usuario = crear_hogar("lucia")
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


@pytest.fixture
def postulacion(lucia):
    return postulaciones.postular_transito(lucia, crear_ficha(), "2901-555555")


def test_un_visitante_va_al_ingreso_y_no_cambia_nada(client, postulacion):
    client.logout()
    respuesta = client.post(url(postulacion))
    assert respuesta.status_code == 302
    assert "/cuentas/ingresar/" in respuesta.url
    postulacion.refresh_from_db()
    assert postulacion.estado == Estado.PENDIENTE


def test_solo_acepta_post(client, postulacion):
    assert client.get(url(postulacion)).status_code == 405
    postulacion.refresh_from_db()
    assert postulacion.estado == Estado.PENDIENTE


def test_el_hogar_retira_su_postulacion_y_vuelve_a_la_ficha(client, postulacion):
    respuesta = client.post(url(postulacion))

    assert respuesta.status_code == 302
    assert respuesta.url == f"{ficha_url(postulacion.ficha)}?retirada=1"
    postulacion.refresh_from_db()
    assert postulacion.estado == Estado.DESCARTADA


def test_la_postulacion_de_otra_persona_da_404_y_no_cambia(client, lucia):
    martin = crear_hogar("martin")
    ajena = postulaciones.postular_transito(martin, crear_ficha(), "2901-111111")

    assert client.post(url(ajena)).status_code == 404

    ajena.refresh_from_db()
    assert ajena.estado == Estado.PENDIENTE


def test_una_postulacion_inexistente_da_404(client, lucia):
    respuesta = client.post(reverse("transito:retirar_postulacion", args=[999999]))
    assert respuesta.status_code == 404


@pytest.mark.parametrize("estado", [Estado.ELEGIDA, Estado.DESCARTADA, Estado.CONCRETADA])
def test_una_postulacion_que_ya_no_esta_pendiente_vuelve_a_la_ficha_sin_cambios(
    client, postulacion, estado
):
    Postulacion.objects.filter(pk=postulacion.pk).update(estado=estado)

    respuesta = client.post(url(postulacion))

    assert respuesta.status_code == 302
    assert respuesta.url == ficha_url(postulacion.ficha)
    postulacion.refresh_from_db()
    assert postulacion.estado == estado


def test_una_cuenta_suspendida_ve_la_pagina_de_suspension_y_no_cambia_nada(
    client, lucia, postulacion
):
    Sancion.objects.create(
        usuario=lucia,
        email_hash=lucia.email_hash,
        tipo=Sancion.Tipo.TEMPORAL,
        motivo="Motivo de prueba",
        fin=timezone.now() + timedelta(days=3),
    )

    respuesta = client.post(url(postulacion))

    assert respuesta.status_code == 403
    postulacion.refresh_from_db()
    assert postulacion.estado == Estado.PENDIENTE


def test_despues_de_retirarla_se_puede_volver_a_postular(client, lucia, postulacion):
    client.post(url(postulacion))

    respuesta = client.get(reverse("transito:postular", args=[postulacion.ficha_id]))

    assert respuesta.status_code == 200
    assert 'name="contacto"' in respuesta.content.decode()
