import pytest
from django.db import IntegrityError
from django.urls import reverse

from apps.cuentas.forms import RegistroForm
from apps.cuentas.models import EstadoCuenta, Usuario
from apps.cuentas.views import MENSAJE_ERROR_GENERAL

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"


def datos(**cambios):
    base = {
        "nombre_usuario": "Ana",
        "email": "ana@example.com",
        "password1": CLAVE,
        "password2": CLAVE,
        "acepta_condiciones": "on",
    }
    return {**base, **cambios}


@pytest.mark.django_db
def test_la_pagina_de_registro_carga(client):
    respuesta = client.get(reverse("cuentas:registro"))
    assert respuesta.status_code == 200
    html = respuesta.content.decode()
    assert "Crear cuenta" in html
    assert "Sin conexión a internet, conéctese a una red para registrarse" in html


@pytest.mark.django_db
def test_registro_correcto_crea_la_cuenta_y_redirige(client):
    respuesta = client.post(reverse("cuentas:registro"), datos())
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("cuentas:registro_listo")
    usuario = Usuario.objects.get(email="ana@example.com")
    assert usuario.estado_cuenta == EstadoCuenta.PENDIENTE


@pytest.mark.django_db
def test_la_pagina_de_cuenta_creada_carga(client):
    respuesta = client.get(reverse("cuentas:registro_listo"))
    assert respuesta.status_code == 200
    assert "Cuenta creada" in respuesta.content.decode()


@pytest.mark.django_db
def test_registro_con_errores_muestra_los_mensajes_y_no_crea_la_cuenta(client):
    mala = datos(password1="Zq7mWp3xK", password2="Zq7mWp3xK", acepta_condiciones="")
    respuesta = client.post(reverse("cuentas:registro"), mala)
    assert respuesta.status_code == 200
    html = respuesta.content.decode()
    assert "La contraseña debe tener al menos 10 caracteres" in html
    assert "Debe aceptar las condiciones de uso y la política de datos" in html
    assert Usuario.objects.count() == 0


@pytest.mark.django_db
def test_con_errores_conserva_el_nombre_pero_nunca_devuelve_la_contrasena(client):
    respuesta = client.post(reverse("cuentas:registro"), datos(password2="otra-clave-distinta-2"))
    html = respuesta.content.decode()
    assert 'value="Ana"' in html
    assert "Las contraseñas no coinciden" in html
    assert CLAVE not in html


@pytest.mark.django_db
def test_si_la_base_rechaza_el_alta_se_muestra_un_error(client, monkeypatch):
    def falla(self):
        raise IntegrityError

    monkeypatch.setattr(RegistroForm, "save", falla)
    respuesta = client.post(reverse("cuentas:registro"), datos())
    assert respuesta.status_code == 200
    assert MENSAJE_ERROR_GENERAL in respuesta.content.decode()


@pytest.mark.django_db
def test_un_usuario_con_sesion_iniciada_es_redirigido(client):
    usuario = Usuario.objects.create_user(
        "luis@example.com", "Luis", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND_MODELO)
    respuesta = client.get(reverse("cuentas:registro"))
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("core:inicio")
