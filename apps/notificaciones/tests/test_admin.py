import pytest
from django.urls import reverse

from apps.notificaciones.models import Notificacion
from apps.notificaciones.servicios import notificar

from .conftest import BACKEND_MODELO, CLAVE

pytestmark = pytest.mark.django_db


def test_el_admin_busca_por_correo_del_usuario(client, django_user_model, ana, beto):
    notificar(ana, Notificacion.Tipo.EVENTO, "Aviso para Ana")
    notificar(beto, Notificacion.Tipo.EVENTO, "Aviso para Beto")
    admin = django_user_model.objects.create_superuser("root@ejemplo.com", "Root", CLAVE)
    client.force_login(admin, backend=BACKEND_MODELO)

    respuesta = client.get(
        reverse("admin:notificaciones_notificacion_changelist"), {"q": ana.email}
    )

    assert respuesta.status_code == 200
    assert "Aviso para Ana" in respuesta.content.decode()
    assert "Aviso para Beto" not in respuesta.content.decode()
