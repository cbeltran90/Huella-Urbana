from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import EstadoCuenta, Rol, Sancion, Usuario
from apps.fichas.models import FichaAnimal

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"

pytestmark = pytest.mark.django_db


def crear_usuario(nombre, **campos):
    return Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, **campos
    )


def crear_ficha(**campos):
    datos = {
        "nombre": "Bruno",
        "especie": "perro",
        "tamano": "mediano",
        "estado": FichaAnimal.Estado.SIN_RESPONSABLE,
        "es_privada": True,
        **campos,
    }
    return FichaAnimal.objects.create(**datos)


def detalle(client, ficha, consulta=""):
    return client.get(reverse("fichas:detalle", args=[ficha.pk]) + consulta).content.decode()


def enlace(ficha):
    return reverse("transito:solicitar", args=[ficha.pk])


@pytest.fixture
def carla(client):
    usuario = crear_usuario("carla")
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


def test_el_cuidador_ve_el_boton(client, carla):
    ficha = crear_ficha(cuidador=carla)
    assert enlace(ficha) in detalle(client, ficha)


def test_un_moderador_ve_el_boton(client):
    moderadora = crear_usuario("mora", rol=Rol.MODERADOR)
    client.force_login(moderadora, backend=BACKEND_MODELO)
    ficha = crear_ficha(cuidador=None)
    assert enlace(ficha) in detalle(client, ficha)


def test_otro_usuario_no_ve_el_boton(client, carla):
    ficha = crear_ficha(cuidador=crear_usuario("otra"), es_privada=False)
    assert enlace(ficha) not in detalle(client, ficha)


def test_un_visitante_no_ve_el_boton(client):
    ficha = crear_ficha(cuidador=crear_usuario("otra"), es_privada=False)
    assert enlace(ficha) not in detalle(client, ficha)


@pytest.mark.parametrize(
    "estado",
    [
        FichaAnimal.Estado.REGISTRADO,
        FichaAnimal.Estado.EN_ADOPCION,
        FichaAnimal.Estado.EN_TRANSITO,
    ],
)
def test_con_otro_estado_no_se_ve_el_boton(client, carla, estado):
    ficha = crear_ficha(cuidador=carla, estado=estado, es_privada=False)
    assert enlace(ficha) not in detalle(client, ficha)


def test_una_cuenta_suspendida_no_ve_el_boton(client, carla):
    Sancion.objects.create(
        usuario=carla,
        email_hash=carla.email_hash,
        tipo=Sancion.Tipo.TEMPORAL,
        motivo="Motivo de prueba",
        fin=timezone.now() + timedelta(days=3),
    )
    ficha = crear_ficha(cuidador=carla, es_privada=False)
    assert enlace(ficha) not in detalle(client, ficha)


def test_despues_de_solicitar_se_ve_el_aviso(client, carla):
    ficha = crear_ficha(cuidador=carla, estado=FichaAnimal.Estado.EN_ADOPCION, es_privada=False)
    assert "quedó pública" in detalle(client, ficha, "?solicitado=1")


def test_sin_el_parametro_no_se_ve_el_aviso(client, carla):
    ficha = crear_ficha(cuidador=carla, estado=FichaAnimal.Estado.EN_ADOPCION, es_privada=False)
    assert "quedó pública" not in detalle(client, ficha)


def test_el_aviso_no_se_ve_para_quien_no_la_pidio(client, carla):
    ficha = crear_ficha(
        cuidador=crear_usuario("otra"), estado=FichaAnimal.Estado.EN_ADOPCION, es_privada=False
    )
    assert "quedó pública" not in detalle(client, ficha, "?solicitado=1")
