import re

import pytest
from django.conf import settings
from django.contrib.gis.geos import Point
from django.urls import reverse
from model_bakery import baker

from apps.notificaciones.models import Notificacion
from apps.notificaciones.servicios import notificar
from apps.publicaciones.models import Publicacion

Tipo = Notificacion.Tipo
MIS_AVISOS = reverse("notificaciones:mis_avisos")

pytestmark = pytest.mark.django_db


def test_sin_sesion_va_al_ingreso(client):
    respuesta = client.get(MIS_AVISOS)

    assert respuesta.status_code == 302
    assert respuesta.url.startswith(settings.LOGIN_URL)


def test_muestra_solo_los_avisos_propios(entrar, ana, beto):
    notificar(ana, Tipo.EVENTO, "Aviso para Ana")
    notificar(beto, Tipo.EVENTO, "Aviso para Beto")

    html = entrar(ana).get(MIS_AVISOS).content.decode()

    assert "Aviso para Ana" in html
    assert "Aviso para Beto" not in html


def test_la_primera_vez_lo_muestra_como_nuevo_y_lo_marca_leido(entrar, ana):
    aviso = notificar(ana, Tipo.EVENTO, "Jornada de vacunación")
    cliente = entrar(ana)

    primera = cliente.get(MIS_AVISOS).content.decode()
    segunda = cliente.get(MIS_AVISOS).content.decode()

    aviso.refresh_from_db()
    assert aviso.leida is True
    assert "Nuevo" in primera
    assert "Nuevo" not in segunda


def test_enlaza_a_la_publicacion(entrar, ana):
    publicacion = baker.make(
        Publicacion,
        tipo=Publicacion.Tipo.EXTRAVIO,
        ubicacion=Point(-68.3040, -54.8025, srid=4326),
    )
    notificar(ana, Tipo.FAVORITO, "Novedad", publicacion=publicacion)

    html = entrar(ana).get(MIS_AVISOS).content.decode()

    assert reverse("publicaciones:detalle", args=[publicacion.pk]) in html


def test_sin_avisos_lo_dice(entrar, ana):
    html = entrar(ana).get(MIS_AVISOS).content.decode()
    assert "No tenés avisos." in html


def test_el_menu_cuenta_los_sin_leer_y_se_vacia_al_abrir_la_pagina(entrar, ana):
    notificar(ana, Tipo.EVENTO, "Uno")
    notificar(ana, Tipo.EVENTO, "Dos")
    cliente = entrar(ana)

    antes = cliente.get(reverse("core:inicio")).content.decode()
    cliente.get(MIS_AVISOS)
    despues = cliente.get(reverse("core:inicio")).content.decode()

    assert re.search(r'id="avisos-sin-leer"[^>]*>\s*2\s*<', antes)
    assert "Avisos" in despues and "avisos-sin-leer" not in despues
