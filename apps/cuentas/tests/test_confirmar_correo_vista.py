import pytest
from django.urls import reverse

from apps.cuentas import servicios
from apps.cuentas.models import EstadoCuenta, Usuario

CLAVE = "clave-de-prueba-1"
NUEVO = "nuevo@example.com"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"


@pytest.fixture
def ana(db):
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def enlace(ana, correo=NUEVO):
    return reverse(
        "cuentas:confirmar_correo", args=[servicios.crear_token_cambio_correo(ana, correo)]
    )


@pytest.mark.django_db
def test_el_enlace_cambia_el_correo_sin_necesitar_sesion(client, ana):
    respuesta = client.get(enlace(ana))

    assert respuesta.status_code == 200
    assert "Actualizamos el correo" in respuesta.content.decode()
    ana.refresh_from_db()
    assert ana.email == NUEVO


@pytest.mark.django_db
def test_sin_sesion_se_ofrece_ingresar(client, ana):
    contenido = client.get(enlace(ana)).content.decode()
    assert reverse("cuentas:login") in contenido


@pytest.mark.django_db
def test_con_sesion_se_ofrece_volver_al_perfil(client, ana):
    client.force_login(ana, backend=BACKEND_MODELO)
    contenido = client.get(enlace(ana)).content.decode()
    assert reverse("cuentas:perfil") in contenido


@pytest.mark.django_db
def test_un_enlace_falso_da_400_y_no_cambia_nada(client, ana):
    respuesta = client.get(reverse("cuentas:confirmar_correo", args=["token-falso"]))
    assert respuesta.status_code == 400
    assert "No pudimos cambiar el correo" in respuesta.content.decode()
    ana.refresh_from_db()
    assert ana.email == "ana@example.com"


@pytest.mark.django_db
def test_un_enlace_usado_da_400(client, ana):
    ruta = enlace(ana)
    assert client.get(ruta).status_code == 200
    respuesta = client.get(ruta)
    assert respuesta.status_code == 400
    assert servicios.MENSAJE_ENLACE_CORREO_INVALIDO in respuesta.content.decode()
