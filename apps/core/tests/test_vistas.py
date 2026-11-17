import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_salud_responde_ok(client):
    respuesta = client.get(reverse("core:salud"))
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


@pytest.mark.django_db
def test_el_inicio_muestra_el_mapa(client):
    respuesta = client.get(reverse("core:inicio"))

    assert respuesta.status_code == 200
    assert "mapa/mapa.html" in [plantilla.name for plantilla in respuesta.templates]


@pytest.mark.django_db
def test_la_prueba_del_stack_ya_no_existe(client):
    assert client.get("/prueba/").status_code == 404


@pytest.mark.django_db
def test_todas_las_paginas_enlazan_el_icono_del_sitio(client):
    html = client.get(reverse("core:inicio")).content.decode()

    assert 'rel="icon" href="/static/img/favicon.ico"' in html
    assert 'href="/static/img/favicon.svg" type="image/svg+xml"' in html
    assert 'rel="apple-touch-icon" href="/static/img/apple-touch-icon.png"' in html
