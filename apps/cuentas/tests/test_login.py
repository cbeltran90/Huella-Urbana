import pytest
from django.conf import settings
from django.shortcuts import resolve_url
from django.urls import reverse

from apps.cuentas.forms import MENSAJE_LOGIN_INVALIDO
from apps.cuentas.models import EstadoCuenta, Usuario

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def entrar(client, email="ana@example.com", clave=CLAVE, **extra):
    return client.post(reverse("cuentas:login"), {"username": email, "password": clave, **extra})


def hay_sesion(client):
    return "_auth_user_id" in client.session


@pytest.mark.django_db
def test_la_pagina_de_ingreso_carga(client):
    respuesta = client.get(reverse("cuentas:login"))
    assert respuesta.status_code == 200
    assert "Ingresar" in respuesta.content.decode()


@pytest.mark.django_db
def test_ingresar_con_el_correo_y_la_clave_correctos(client, ana):
    respuesta = entrar(client)
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("core:inicio")
    assert client.session["_auth_user_id"] == str(ana.pk)


@pytest.mark.django_db
def test_el_correo_no_distingue_mayusculas_ni_espacios(client, ana):
    assert entrar(client, "  ANA@Example.com ").status_code == 302
    assert hay_sesion(client)


@pytest.mark.django_db
def test_clave_incorrecta_muestra_el_mensaje_del_caso_de_uso(client, ana):
    respuesta = entrar(client, clave="otra-clave-equivocada")
    assert respuesta.status_code == 200
    assert MENSAJE_LOGIN_INVALIDO in respuesta.content.decode()
    assert not hay_sesion(client)


@pytest.mark.django_db
def test_un_correo_inexistente_da_el_mismo_mensaje(client, ana):
    respuesta = entrar(client, "nadie@example.com")
    assert respuesta.status_code == 200
    assert MENSAJE_LOGIN_INVALIDO in respuesta.content.decode()


@pytest.mark.django_db
def test_una_cuenta_eliminada_no_entra_y_recibe_el_mismo_mensaje(client):
    Usuario.objects.create_user(
        "baja@example.com", "Baja", CLAVE, estado_cuenta=EstadoCuenta.ELIMINADA
    )
    respuesta = entrar(client, "baja@example.com")
    assert MENSAJE_LOGIN_INVALIDO in respuesta.content.decode()
    assert not hay_sesion(client)


@pytest.mark.django_db
def test_despues_de_ingresar_vuelve_a_la_pagina_pedida(client, ana):
    respuesta = entrar(client, next=reverse("core:salud"))
    assert respuesta.url == reverse("core:salud")


@pytest.mark.django_db
def test_un_destino_de_otro_sitio_se_ignora(client, ana):
    respuesta = entrar(client, next="https://sitio-ajeno.example/")
    assert respuesta.url == reverse("core:inicio")


@pytest.mark.django_db
def test_un_usuario_con_sesion_es_redirigido(client, ana):
    client.force_login(ana, backend=BACKEND_MODELO)
    respuesta = client.get(reverse("cuentas:login"))
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("core:inicio")


@pytest.mark.django_db
def test_cerrar_sesion_solo_funciona_por_post(client, ana):
    client.force_login(ana, backend=BACKEND_MODELO)
    assert client.get(reverse("cuentas:logout")).status_code == 405
    assert hay_sesion(client)
    respuesta = client.post(reverse("cuentas:logout"))
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("core:inicio")
    assert not hay_sesion(client)


def test_las_paginas_protegidas_mandan_a_la_pantalla_de_ingreso():
    assert resolve_url(settings.LOGIN_URL) == reverse("cuentas:login")
