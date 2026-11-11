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
