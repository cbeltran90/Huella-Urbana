import pytest
from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.urls import reverse

from apps.cuentas.models import EstadoCuenta, Rol, Usuario

CLAVE = "clave-de-prueba-1"

pytestmark = pytest.mark.django_db


def menu(rf, usuario):
    request = rf.get("/")
    request.user = usuario
    return render_to_string("componentes/_nav.html", request=request)


def cuenta(rol=Rol.REGISTRADO):
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, rol=rol
    )


def test_sin_sesion_no_ofrece_los_enlaces_de_perfil(rf):
    html = menu(rf, AnonymousUser())

    assert reverse("cuentas:perfil_adoptante") not in html
    assert reverse("transito:perfil_transito") not in html
    assert reverse("admin:index") not in html


def test_con_sesion_ofrece_hogar_y_familia_y_hogar_de_transito(rf):
    html = menu(rf, cuenta())

    assert reverse("cuentas:perfil_adoptante") in html
    assert reverse("transito:perfil_transito") in html


def test_un_usuario_comun_no_ve_moderacion(rf):
    assert reverse("admin:index") not in menu(rf, cuenta())


@pytest.mark.parametrize("rol", [Rol.MODERADOR, Rol.ADMINISTRADOR])
def test_moderadores_y_administradores_ven_moderacion(rf, rol):
    assert reverse("admin:index") in menu(rf, cuenta(rol))
