"""Casos borde de cuentas que no tenían prueba: errores poco frecuentes y textos de las filas."""

import re

import pytest
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.gis.geos import Point
from django.core.cache import caches
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.cuentas import servicios
from apps.cuentas.forms import (
    MENSAJE_CLAVE_CORTA,
    InicioSesionForm,
    NombreUsuarioForm,
    RegistroForm,
)
from apps.cuentas.models import Domicilio, EstadoCuenta, PerfilAdoptante, Sancion, Usuario

CLAVE = "clave-de-prueba-1"
CLAVE_NUMERICA = "1234567890123"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"
NUEVO = "nuevo@example.com"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def sin_esperas():
    caches["reenvios"].clear()
    yield
    caches["reenvios"].clear()


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


@pytest.fixture
def ana_con_sesion(client, ana):
    client.force_login(ana, backend=BACKEND_MODELO)
    return ana


@pytest.fixture
def root(client):
    usuario = Usuario.objects.create_superuser("root@example.com", "Root", CLAVE)
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


# --- Contraseñas inválidas que no son "muy corta" ---


def test_el_registro_rechaza_una_contrasena_solo_numerica():
    form = RegistroForm(
        {
            "nombre_usuario": "Ana",
            "email": "ana@example.com",
            "password1": CLAVE_NUMERICA,
            "password2": CLAVE_NUMERICA,
            "acepta_condiciones": "on",
        }
    )

    assert not form.is_valid()
    assert form.errors["password1"]
    assert MENSAJE_CLAVE_CORTA not in form.errors["password1"]


def test_el_cambio_de_contrasena_rechaza_una_contrasena_solo_numerica(client, ana_con_sesion):
    respuesta = client.post(
        reverse("cuentas:cambiar_contrasena"),
        {
            "old_password": CLAVE,
            "new_password1": CLAVE_NUMERICA,
            "new_password2": CLAVE_NUMERICA,
        },
    )

    assert respuesta.status_code == 200
    ana_con_sesion.refresh_from_db()
    assert ana_con_sesion.check_password(CLAVE)


# --- Inicio de sesión y recuperación ---


def test_sin_datos_el_formulario_de_ingreso_no_toma_la_cuenta_por_pendiente():
    form = InicioSesionForm(data={})

    assert not form.is_valid()
    assert form._es_cuenta_pendiente() is False


def test_si_falla_el_envio_de_la_recuperacion_la_respuesta_sigue_igual(client, ana, monkeypatch):
    def falla(*args, **kwargs):
        raise OSError

    monkeypatch.setattr(PasswordResetForm, "send_mail", falla)

    respuesta = client.post(reverse("cuentas:recuperar"), {"email": "ana@example.com"})

    assert respuesta.status_code == 302
    assert respuesta.url == reverse("cuentas:recuperar_listo")


def test_las_pantallas_de_reenvio_cargan(client):
    assert client.get(reverse("cuentas:reenviar")).status_code == 200
    assert client.get(reverse("cuentas:reenvio_listo")).status_code == 200


# --- Perfiles: errores que llegan desde el servicio o el formulario ---


def test_un_error_del_servicio_de_adopcion_se_muestra_en_el_campo(
    client, ana_con_sesion, monkeypatch
):
    def rechaza(*args, **kwargs):
        raise servicios.PerfilAdoptanteInvalido("Texto de error de prueba")

    monkeypatch.setattr(servicios, "guardar_perfil_adoptante", rechaza)

    respuesta = client.post(reverse("cuentas:perfil_adoptante"), {"experiencia_previa": "Algo"})

    assert respuesta.status_code == 200
    assert "Texto de error de prueba" in respuesta.content.decode()


def test_un_error_al_guardar_el_nombre_se_muestra_en_el_campo(client, ana_con_sesion, monkeypatch):
    def rechaza(*args, **kwargs):
        raise ValidationError("Nombre ya usado")

    monkeypatch.setattr(NombreUsuarioForm, "save", rechaza)

    respuesta = client.post(reverse("cuentas:editar_perfil"), {"nombre_usuario": "Nuevo"})

    assert respuesta.status_code == 200
    assert "Nombre ya usado" in respuesta.content.decode()


def test_si_otra_persona_toma_el_correo_justo_antes_de_guardar_se_avisa(
    ana, mailoutbox, monkeypatch
):
    servicios.solicitar_cambio_correo(ana, NUEVO, RequestFactory().get("/"))
    token = re.search(r"/cuentas/correo/confirmar/([^/\s]+)/", mailoutbox[-1].body).group(1)

    def choca(*args, **kwargs):
        raise IntegrityError

    monkeypatch.setattr(Usuario, "save", choca)

    with pytest.raises(servicios.CambioCorreoInvalido) as error:
        servicios.confirmar_cambio_correo(token)

    assert str(error.value) == servicios.MENSAJE_CORREO_USADO


# --- Panel de sanciones ---


def test_la_accion_de_levantar_avisa_si_la_sancion_ya_no_esta_vigente(client, root, ana):
    sancion = Sancion.objects.create(
        usuario=ana,
        email_hash=ana.email_hash,
        tipo=Sancion.Tipo.PERMANENTE,
        motivo="Motivo de prueba",
        aplicada_por=root,
        revocada_en=timezone.now(),
    )

    respuesta = client.post(
        reverse("admin:cuentas_sancion_changelist"),
        {"action": "levantar", "_selected_action": [sancion.pk]},
        follow=True,
    )

    assert "La sanción ya no está vigente" in respuesta.content.decode()


# --- Modelos ---


def test_un_superusuario_tiene_que_ser_staff_y_superusuario():
    with pytest.raises(ValueError, match="is_staff"):
        Usuario.objects.create_superuser("a@example.com", "A", CLAVE, is_staff=False)
    with pytest.raises(ValueError, match="is_superuser"):
        Usuario.objects.create_superuser("b@example.com", "B", CLAVE, is_superuser=False)


def test_el_domicilio_y_el_perfil_de_adopcion_se_nombran_por_su_dueno(ana):
    punto = Point(-68.3100, -54.8100, srid=4326)
    domicilio = Domicilio.objects.create(usuario=ana, ubicacion=punto, ubicacion_desplazada=punto)
    perfil = PerfilAdoptante.objects.create(usuario=ana, experiencia_previa="Tuve un perro.")

    assert str(domicilio) == "Domicilio de Ana"
    assert str(perfil) == "Perfil de adoptante de Ana"
