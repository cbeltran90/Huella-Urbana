import pytest
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.urls import reverse

from apps.cuentas.models import EstadoCuenta, Usuario

CLAVE = "clave-de-prueba-1"


def menu(rf, usuario):
    request = rf.get("/")
    request.user = usuario
    return render_to_string("cuentas/_menu_sesion.html", request=request)


def test_sin_sesion_ofrece_ingresar_y_crear_cuenta(rf):
    html = menu(rf, AnonymousUser())
    assert reverse("cuentas:login") in html
    assert reverse("cuentas:registro") in html
    assert reverse("cuentas:logout") not in html


@pytest.mark.django_db
def test_con_sesion_muestra_el_nombre_y_cierra_sesion_por_post(rf):
    usuario = Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    html = menu(rf, usuario)
    assert "Ana" in html
    assert reverse("cuentas:logout") in html
    assert 'method="post"' in html
    assert "csrfmiddlewaretoken" in html
    assert reverse("cuentas:login") not in html
