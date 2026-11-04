import pytest
from django.test import Client
from django.urls import reverse

from apps.cuentas import servicios
from apps.cuentas.forms import (
    MENSAJE_CLAVE_ACTUAL_INCORRECTA,
    MENSAJE_CLAVE_CORTA,
    MENSAJE_CLAVES_DISTINTAS,
)
from apps.cuentas.models import EstadoCuenta, Rol, Sancion, Usuario

CLAVE = "clave-de-prueba-1"
NUEVA = "nueva-clave-77"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"


def url():
    return reverse("cuentas:cambiar_contrasena")


@pytest.fixture
def ana(client):
    usuario = Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


def cambiar(client, actual=CLAVE, nueva=NUEVA, confirmacion=None):
    return client.post(
        url(),
        {
            "old_password": actual,
            "new_password1": nueva,
            "new_password2": nueva if confirmacion is None else confirmacion,
        },
    )


@pytest.mark.django_db
def test_un_visitante_va_al_ingreso(client):
    respuesta = client.get(url())
    assert respuesta.status_code == 302
    assert respuesta.url.startswith("/cuentas/ingresar/?next=")


@pytest.mark.django_db
def test_una_cuenta_suspendida_recibe_403_y_no_cambia_la_clave(client, ana):
    moderadora = Usuario.objects.create_user(
        "mod@example.com", "Mod", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, rol=Rol.MODERADOR
    )
    servicios.sancionar(ana, Sancion.Tipo.PERMANENTE, "Motivo", moderadora)

    assert client.get(url()).status_code == 403
    assert cambiar(client).status_code == 403
    ana.refresh_from_db()
    assert ana.check_password(CLAVE)


@pytest.mark.django_db
def test_la_pantalla_pide_las_tres_contrasenas(client, ana):
    contenido = client.get(url()).content.decode()
    for campo in ("old_password", "new_password1", "new_password2"):
        assert f'name="{campo}"' in contenido


@pytest.mark.django_db
def test_se_cambia_la_contrasena_y_se_vuelve_al_perfil(client, ana):
    respuesta = cambiar(client)

    assert respuesta.status_code == 302
    assert respuesta.url == f"{reverse('cuentas:perfil')}?guardado=1"
    ana.refresh_from_db()
    assert ana.check_password(NUEVA)
    assert not ana.check_password(CLAVE)


@pytest.mark.django_db
def test_la_sesion_actual_sigue_abierta(client, ana):
    cambiar(client)
    assert client.get(reverse("cuentas:perfil")).status_code == 200


@pytest.mark.django_db
def test_las_otras_sesiones_se_cierran(client, ana):
    otra = Client()
    otra.force_login(ana, backend=BACKEND_MODELO)
    assert otra.get(reverse("cuentas:perfil")).status_code == 200

    cambiar(client)

    assert otra.get(reverse("cuentas:perfil")).status_code == 302


@pytest.mark.django_db
def test_una_contrasena_actual_incorrecta_se_rechaza(client, ana):
    respuesta = cambiar(client, actual="otra-clave-distinta")
    assert respuesta.status_code == 200
    assert MENSAJE_CLAVE_ACTUAL_INCORRECTA in respuesta.content.decode()
    ana.refresh_from_db()
    assert ana.check_password(CLAVE)


@pytest.mark.django_db
def test_una_contrasena_nueva_corta_se_rechaza(client, ana):
    respuesta = cambiar(client, nueva="zorro-az9")
    assert respuesta.status_code == 200
    assert MENSAJE_CLAVE_CORTA in respuesta.content.decode()
    ana.refresh_from_db()
    assert ana.check_password(CLAVE)


@pytest.mark.django_db
def test_las_contrasenas_nuevas_distintas_se_rechazan(client, ana):
    respuesta = cambiar(client, confirmacion="nueva-clave-88")
    assert respuesta.status_code == 200
    assert MENSAJE_CLAVES_DISTINTAS in respuesta.content.decode()
    ana.refresh_from_db()
    assert ana.check_password(CLAVE)
