import pytest
from django.contrib import admin
from django.urls import reverse

from apps.cuentas.models import EstadoCuenta, Rol, Usuario
from apps.transito import servicios
from apps.transito.models import PerfilTransito

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"


@pytest.fixture
def moderador(client):
    usuario = Usuario.objects.create_user(
        "mod@example.com", "Moderadora", CLAVE, rol=Rol.MODERADOR, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


@pytest.fixture
def administrador(client):
    usuario = Usuario.objects.create_superuser("root@example.com", "Root", CLAVE)
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def crear_perfil(usuario, **campos):
    datos = {
        "especies_aceptadas": "perro",
        "tamano_maximo": "mediano",
        "duracion_maxima_dias": 30,
        "cupo_declarado": 2,
        **campos,
    }
    return PerfilTransito.objects.create(usuario=usuario, **datos)


def columna():
    return admin.site._registry[Usuario].hogar_de_transito


@pytest.mark.django_db
def test_la_columna_dice_si_la_persona_es_hogar_de_transito(ana):
    assert columna()(ana) is False

    crear_perfil(ana)

    assert columna()(ana) is True


@pytest.mark.django_db
def test_con_el_perfil_desactivado_la_columna_dice_que_no(ana):
    crear_perfil(ana, activo=False)

    assert columna()(ana) is False


@pytest.mark.django_db
def test_al_retirar_el_rol_la_columna_cambia(ana, moderador):
    crear_perfil(ana)

    servicios.retirar_rol_transito(ana, moderador)

    assert columna()(ana) is False


@pytest.mark.django_db
def test_la_lista_de_usuarios_muestra_la_columna(client, moderador, ana):
    respuesta = client.get(reverse("admin:cuentas_usuario_changelist"))

    assert respuesta.status_code == 200
    assert "Hogar de tránsito" in respuesta.content.decode()


@pytest.mark.django_db
def test_el_moderador_ve_el_dato_en_el_detalle_del_usuario(client, moderador, ana):
    respuesta = client.get(reverse("admin:cuentas_usuario_change", args=[ana.pk]))

    assert respuesta.status_code == 200
    assert "Hogar de tránsito" in respuesta.content.decode()


@pytest.mark.django_db
def test_el_administrador_ve_el_dato_en_el_detalle_del_usuario(client, administrador, ana):
    respuesta = client.get(reverse("admin:cuentas_usuario_change", args=[ana.pk]))

    assert respuesta.status_code == 200
    assert "Hogar de tránsito" in respuesta.content.decode()


@pytest.mark.django_db
def test_el_dato_no_se_puede_editar_ni_se_pide_al_crear_un_usuario(client, administrador):
    respuesta = client.get(reverse("admin:cuentas_usuario_add"))

    assert respuesta.status_code == 200
    assert 'name="hogar_de_transito"' not in respuesta.content.decode()
