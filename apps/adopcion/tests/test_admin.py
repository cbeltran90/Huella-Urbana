import pytest
from django.urls import reverse
from model_bakery import baker

from apps.adopcion.models import Adopcion
from apps.fichas.models import FichaAnimal

from .conftest import BACKEND_MODELO, CLAVE

pytestmark = pytest.mark.django_db


def test_el_admin_busca_por_correo_del_adoptante(client, django_user_model, ana, beto):
    Adopcion.objects.create(ficha=baker.make(FichaAnimal, nombre="Firulais"), adoptante=ana)
    Adopcion.objects.create(ficha=baker.make(FichaAnimal, nombre="Michi"), adoptante=beto)
    admin = django_user_model.objects.create_superuser("root@ejemplo.com", "Root", CLAVE)
    client.force_login(admin, backend=BACKEND_MODELO)

    respuesta = client.get(reverse("admin:adopcion_adopcion_changelist"), {"q": ana.email})

    assert respuesta.status_code == 200
    assert "Firulais" in respuesta.content.decode()
    assert "Michi" not in respuesta.content.decode()
