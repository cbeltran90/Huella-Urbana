from datetime import timedelta

import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import Domicilio, EstadoCuenta, Rol, Sancion, Usuario
from apps.cuentas.servicios import guardar_domicilio
from apps.fichas.models import FichaAnimal
from apps.publicaciones.models import Publicacion

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"
PUNTO = Point(-68.3040, -54.8025, srid=4326)  # dentro de Ushuaia
MARCADO = {"latitud": "-54.8025", "longitud": "-68.3040"}

pytestmark = pytest.mark.django_db


def crear_usuario(nombre, **campos):
    return Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, **campos
    )


def crear_ficha(**campos):
    datos = {
        "nombre": "Bruno",
        "especie": "perro",
        "tamano": "mediano",
        "estado": FichaAnimal.Estado.SIN_RESPONSABLE,
        "es_privada": True,
        **campos,
    }
    return FichaAnimal.objects.create(**datos)


def url(ficha):
    return reverse("transito:solicitar", args=[ficha.pk])


@pytest.fixture
def carla(client):
    """Cuidadora con domicilio: no hace falta marcar el punto."""
    usuario = crear_usuario("carla")
    guardar_domicilio(usuario, PUNTO)
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


@pytest.fixture
def dani(client):
    """Cuidador sin domicilio: hay que marcar el punto."""
    usuario = crear_usuario("dani")
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


@pytest.fixture
def mora(client):
    usuario = crear_usuario("mora", rol=Rol.MODERADOR)
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


# Acceso


def test_un_visitante_va_al_ingreso(client):
    respuesta = client.get(url(crear_ficha()))
    assert respuesta.status_code == 302
    assert "/cuentas/ingresar/" in respuesta.url


def test_una_cuenta_suspendida_ve_la_pagina_de_suspension(client, carla):
    Sancion.objects.create(
        usuario=carla,
        email_hash=carla.email_hash,
        tipo=Sancion.Tipo.TEMPORAL,
        motivo="Motivo de prueba",
        fin=timezone.now() + timedelta(days=3),
    )
    respuesta = client.get(url(crear_ficha(cuidador=carla)))
    assert respuesta.status_code == 403
    assert "Tu cuenta está suspendida" in respuesta.content.decode()


def test_la_ficha_inexistente_da_404(client, carla):
    assert client.get(reverse("transito:solicitar", args=[999999])).status_code == 404


def test_una_ficha_privada_ajena_da_404(client, carla):
    assert client.get(url(crear_ficha(cuidador=crear_usuario("otra")))).status_code == 404


def test_una_ficha_publica_ajena_da_403(client, carla):
    ficha = crear_ficha(cuidador=crear_usuario("otra"), es_privada=False)
    assert client.get(url(ficha)).status_code == 403


def test_con_otro_estado_da_403(client, carla):
    ficha = crear_ficha(cuidador=carla, estado=FichaAnimal.Estado.EN_ADOPCION)
    assert client.get(url(ficha)).status_code == 403


# Confirmación


def test_el_cuidador_ve_la_confirmacion_y_no_cambia_nada(client, carla):
    ficha = crear_ficha(cuidador=carla)
    respuesta = client.get(url(ficha))
    assert respuesta.status_code == 200
    assert "Sí, solicitar tránsito" in respuesta.content.decode()
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.SIN_RESPONSABLE
    assert not Publicacion.objects.filter(ficha=ficha).exists()


def test_con_domicilio_no_se_pide_ni_contacto_ni_mapa(client, carla):
    html = client.get(url(crear_ficha(cuidador=carla))).content.decode()
    assert 'name="contacto"' not in html
    assert 'name="latitud"' not in html


def test_sin_domicilio_se_pide_el_mapa_pero_no_el_contacto(client, dani):
    html = client.get(url(crear_ficha(cuidador=dani))).content.decode()
    assert 'name="latitud"' in html
    assert 'name="contacto"' not in html


def test_el_moderador_ve_el_contacto_y_el_mapa_sin_cuidador(client, mora):
    html = client.get(url(crear_ficha(cuidador=None))).content.decode()
    assert 'name="contacto"' in html
    assert 'name="latitud"' in html


# Confirmar


def test_al_confirmar_la_ficha_pasa_a_en_adopcion_y_se_publica(client, carla):
    ficha = crear_ficha(cuidador=carla)
    respuesta = client.post(url(ficha))
    assert respuesta.status_code == 302
    assert respuesta.url == f"{reverse('fichas:detalle', args=[ficha.pk])}?solicitado=1"
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.EN_ADOPCION
    assert ficha.es_privada is False
    assert Publicacion.objects.filter(ficha=ficha, tipo=Publicacion.Tipo.ADOPCION).count() == 1


def test_sin_domicilio_y_sin_punto_vuelve_con_el_error_y_no_cambia_nada(client, dani):
    ficha = crear_ficha(cuidador=dani)
    respuesta = client.post(url(ficha))
    assert respuesta.status_code == 200
    assert "Marcá en el mapa" in respuesta.content.decode()
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.SIN_RESPONSABLE
    assert not Publicacion.objects.filter(ficha=ficha).exists()


def test_sin_domicilio_con_punto_se_publica_y_queda_como_su_domicilio(client, dani):
    ficha = crear_ficha(cuidador=dani)
    respuesta = client.post(url(ficha), MARCADO)
    assert respuesta.status_code == 302
    assert Domicilio.objects.filter(usuario=dani).exists()
    assert Publicacion.objects.filter(ficha=ficha).count() == 1


def test_un_punto_fuera_de_zona_vuelve_con_el_error(client, dani):
    ficha = crear_ficha(cuidador=dani)
    respuesta = client.post(url(ficha), {"latitud": "0", "longitud": "0"})
    assert respuesta.status_code == 200
    assert "Ushuaia y alrededores" in respuesta.content.decode()
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.SIN_RESPONSABLE


def test_el_moderador_carga_el_contacto_y_el_punto(client, mora):
    ficha = crear_ficha(cuidador=None)
    respuesta = client.post(url(ficha), {"contacto": "Vecina, 2901 555-0101", **MARCADO})
    assert respuesta.status_code == 302
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.EN_ADOPCION
    assert ficha.cuidador_contacto == "Vecina, 2901 555-0101"
    assert Publicacion.objects.get(ficha=ficha).autor == mora


def test_el_moderador_sin_punto_vuelve_con_el_error(client, mora):
    ficha = crear_ficha(cuidador=None)
    respuesta = client.post(url(ficha), {"contacto": "Vecina"})
    assert respuesta.status_code == 200
    assert "Marcá en el mapa" in respuesta.content.decode()
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.SIN_RESPONSABLE


def test_un_contacto_largo_vuelve_con_el_error_y_no_cambia_nada(client, mora):
    ficha = crear_ficha(cuidador=None)
    respuesta = client.post(url(ficha), {"contacto": "x" * 101, **MARCADO})
    assert respuesta.status_code == 200
    assert "no puede superar" in respuesta.content.decode()
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.SIN_RESPONSABLE
    assert not Publicacion.objects.filter(ficha=ficha).exists()
