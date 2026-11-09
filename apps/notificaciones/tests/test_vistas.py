import re

import pytest
from django.conf import settings
from django.contrib.gis.geos import Point
from django.urls import reverse
from model_bakery import baker

from apps.fichas.models import FichaAnimal
from apps.notificaciones.models import Notificacion
from apps.notificaciones.servicios import notificar
from apps.publicaciones.models import Publicacion

Tipo = Notificacion.Tipo
MIS_AVISOS = reverse("notificaciones:mis_avisos")


def abrir(aviso):
    return reverse("notificaciones:abrir", args=[aviso.pk])


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


def test_ver_la_lista_no_marca_los_avisos_como_leidos(entrar, ana):
    aviso = notificar(ana, Tipo.EVENTO, "Jornada de vacunación")
    cliente = entrar(ana)

    cliente.get(MIS_AVISOS)
    segunda = cliente.get(MIS_AVISOS).content.decode()

    aviso.refresh_from_db()
    assert aviso.leida is False
    assert "Nuevo" in segunda


def test_abrir_un_aviso_lo_marca_leido_y_lleva_a_la_publicacion(entrar, ana):
    publicacion = baker.make(
        Publicacion,
        tipo=Publicacion.Tipo.EXTRAVIO,
        ubicacion=Point(-68.3040, -54.8025, srid=4326),
    )
    aviso = notificar(ana, Tipo.FAVORITO, "Novedad", publicacion=publicacion)

    respuesta = entrar(ana).post(abrir(aviso))

    aviso.refresh_from_db()
    assert aviso.leida is True
    assert respuesta.url == reverse("publicaciones:detalle", args=[publicacion.pk])


def test_abrir_un_aviso_de_ficha_lleva_a_la_ficha(entrar, ana):
    ficha = baker.make(FichaAnimal, especie="perro")
    aviso = notificar(ana, Tipo.VINCULACION, "Vincularon tu ficha", ficha=ficha)

    respuesta = entrar(ana).post(abrir(aviso))

    assert respuesta.url == reverse("fichas:detalle", args=[ficha.pk])


def test_un_aviso_sin_destino_se_marca_leido_y_vuelve_a_la_lista(entrar, ana):
    aviso = notificar(ana, Tipo.EVENTO, "Jornada de vacunación")

    respuesta = entrar(ana).post(abrir(aviso))

    aviso.refresh_from_db()
    assert aviso.leida is True
    assert respuesta.url == MIS_AVISOS


def test_no_se_puede_abrir_un_aviso_ajeno(entrar, ana, beto):
    aviso = notificar(beto, Tipo.EVENTO, "Aviso para Beto")

    assert entrar(ana).post(abrir(aviso)).status_code == 404
    aviso.refresh_from_db()
    assert aviso.leida is False


def test_abrir_no_acepta_get(entrar, ana):
    aviso = notificar(ana, Tipo.EVENTO, "Uno")
    assert entrar(ana).get(abrir(aviso)).status_code == 405


def test_sin_avisos_lo_dice(entrar, ana):
    html = entrar(ana).get(MIS_AVISOS).content.decode()
    assert "No tenés avisos." in html


def test_el_menu_cuenta_los_sin_leer_y_baja_al_abrir_uno(entrar, ana):
    uno = notificar(ana, Tipo.EVENTO, "Uno")
    notificar(ana, Tipo.EVENTO, "Dos")
    cliente = entrar(ana)

    antes = cliente.get(reverse("core:inicio")).content.decode()
    cliente.post(abrir(uno))
    despues = cliente.get(reverse("core:inicio")).content.decode()

    assert re.search(r'id="avisos-sin-leer"[^>]*>\s*2\s*<', antes)
    assert re.search(r'id="avisos-sin-leer"[^>]*>\s*1\s*<', despues)


def test_filtra_por_tipo_y_lo_deja_elegido(entrar, ana):
    notificar(ana, Tipo.EVENTO, "Jornada de vacunación")
    notificar(ana, Tipo.NOVEDAD, "Campaña de castración")

    html = entrar(ana).get(MIS_AVISOS, {"tipo": Tipo.EVENTO}).content.decode()

    assert "Jornada de vacunación" in html
    assert "Campaña de castración" not in html
    assert re.search(r'<option value="evento"\s+selected>', html)


def test_solo_ofrece_los_tipos_que_tiene(entrar, ana):
    notificar(ana, Tipo.EVENTO, "Jornada de vacunación")

    html = entrar(ana).get(MIS_AVISOS).content.decode()

    assert 'value="evento"' in html
    assert 'value="alerta_sanitaria"' not in html


def test_un_tipo_que_no_existe_muestra_todos(entrar, ana):
    notificar(ana, Tipo.EVENTO, "Jornada de vacunación")
    notificar(ana, Tipo.NOVEDAD, "Campaña de castración")

    html = entrar(ana).get(MIS_AVISOS, {"tipo": "xyz"}).content.decode()

    assert "Jornada de vacunación" in html and "Campaña de castración" in html


def test_sin_avisos_no_muestra_el_filtro(entrar, ana):
    assert 'name="tipo"' not in entrar(ana).get(MIS_AVISOS).content.decode()
