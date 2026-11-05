import pytest
from django.urls import reverse

from apps.cuentas.models import EstadoCuenta, Usuario
from apps.transito.models import PerfilTransito

CLAVE = "clave-de-prueba-1"
BACKEND = "django.contrib.auth.backends.ModelBackend"


@pytest.fixture
def ana(client):
    usuario = Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND)
    return usuario


def crear_perfil(usuario, **campos):
    datos = {
        "especies_aceptadas": "perro",
        "tamano_maximo": "mediano",
        "duracion_maxima_dias": 30,
        "cupo_declarado": 2,
        **campos,
    }
    return PerfilTransito.objects.create(usuario=usuario, **datos)


@pytest.mark.django_db
def test_sin_perfil_el_perfil_ofrece_completar_el_de_transito(client, ana):
    respuesta = client.get(reverse("cuentas:perfil"))

    contenido = respuesta.content.decode()
    assert respuesta.context["es_hogar_de_transito"] is False
    assert "Hogar de tránsito" in contenido
    assert 'aria-label="Completar el perfil de hogar de tránsito"' in contenido
    assert reverse("transito:perfil_transito") in contenido


@pytest.mark.django_db
def test_con_perfil_activo_el_perfil_ofrece_editarlo(client, ana):
    crear_perfil(ana)

    respuesta = client.get(reverse("cuentas:perfil"))

    contenido = respuesta.content.decode()
    assert respuesta.context["es_hogar_de_transito"] is True
    assert 'aria-label="Editar el perfil de hogar de tránsito"' in contenido
    assert 'aria-label="Completar el perfil de hogar de tránsito"' not in contenido


@pytest.mark.django_db
def test_con_el_perfil_desactivado_vuelve_a_ofrecer_completarlo(client, ana):
    crear_perfil(ana, activo=False)

    respuesta = client.get(reverse("cuentas:perfil"))

    assert respuesta.context["es_hogar_de_transito"] is False
    assert 'aria-label="Completar el perfil de hogar de tránsito"' in respuesta.content.decode()
