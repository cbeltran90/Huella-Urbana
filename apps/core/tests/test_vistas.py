import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_salud_responde_ok(client):
    respuesta = client.get(reverse("core:salud"))
    assert respuesta.status_code == 200
    assert respuesta.json() == {"estado": "ok"}


@pytest.mark.django_db
def test_inicio_y_prueba_cargan(client):
    assert client.get(reverse("core:inicio")).status_code == 200
    assert client.get(reverse("core:prueba")).status_code == 200
