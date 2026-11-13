import pytest
from django.urls import reverse

from apps.cuentas.models import EstadoCuenta, Rol, Usuario
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

pytestmark = pytest.mark.django_db

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"
ACCION = "eliminar_publicacion"


def lista():
    return reverse("admin:publicaciones_publicacion_changelist")


def entrar_como(client, rol):
    usuario = Usuario.objects.create_user(
        "mod@example.com", "Mod", CLAVE, rol=rol, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


def eliminar(client, *publicaciones):
    return client.post(
        lista(), {"action": ACCION, "_selected_action": [p.pk for p in publicaciones]}
    )


@pytest.mark.parametrize("rol", [Rol.MODERADOR, Rol.ADMINISTRADOR])
def test_moderadores_y_administradores_ven_el_listado(client, rol):
    entrar_como(client, rol)

    assert client.get(lista()).status_code == 200


@pytest.mark.parametrize("rol", [Rol.MODERADOR, Rol.ADMINISTRADOR])
def test_la_accion_elimina_las_publicaciones_elegidas(client, ana, rol):
    entrar_como(client, rol)
    una = hacer_publicacion(ana)
    otra = hacer_publicacion(ana)
    queda = hacer_publicacion(ana)

    eliminar(client, una, otra)

    una.refresh_from_db()
    otra.refresh_from_db()
    queda.refresh_from_db()
    assert una.estado == Publicacion.Estado.ELIMINADA
    assert otra.estado == Publicacion.Estado.ELIMINADA
    assert queda.estado == Publicacion.Estado.VIGENTE


def test_un_usuario_comun_no_entra_al_listado(client):
    entrar_como(client, Rol.REGISTRADO)

    assert client.get(lista()).status_code == 302


def test_un_usuario_comun_no_puede_eliminar(client, ana):
    entrar_como(client, Rol.REGISTRADO)
    publicacion = hacer_publicacion(ana)

    eliminar(client, publicacion)

    publicacion.refresh_from_db()
    assert publicacion.estado == Publicacion.Estado.VIGENTE


def test_no_se_puede_crear_ni_borrar_una_publicacion_desde_el_panel(client, ana):
    entrar_como(client, Rol.MODERADOR)
    publicacion = hacer_publicacion(ana)

    assert client.get(reverse("admin:publicaciones_publicacion_add")).status_code == 403
    client.post(lista(), {"action": "delete_selected", "_selected_action": [publicacion.pk]})

    assert Publicacion.objects.filter(pk=publicacion.pk).exists()
