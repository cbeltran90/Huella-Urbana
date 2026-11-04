import pytest
from django.urls import reverse

from apps.cuentas.models import Sancion
from apps.fichas.models import FichaAnimal
from apps.publicaciones.models import Publicacion

from .conftest import crear_imagen, hacer_publicacion

pytestmark = pytest.mark.django_db


@pytest.fixture
def suspendida(ana):
    Sancion.objects.create(
        usuario=ana,
        email_hash=ana.email_hash,
        tipo=Sancion.Tipo.PERMANENTE,
        motivo="Motivo de prueba",
    )
    return ana


def test_una_cuenta_suspendida_no_puede_publicar_un_extravio(entrar, suspendida, con_domicilio):
    datos = {"especie": "perro", "foto": crear_imagen()}

    respuesta = entrar(suspendida).post(reverse("publicaciones:publicar_extravio"), datos)

    assert respuesta.status_code == 403
    assert not Publicacion.objects.exists()
    assert not FichaAnimal.objects.exists()


def test_una_cuenta_suspendida_no_puede_publicar_un_hallazgo(entrar, suspendida):
    datos = {"especie": "perro", "latitud": -54.8, "longitud": -68.3, "foto": crear_imagen()}

    respuesta = entrar(suspendida).post(reverse("publicaciones:publicar_hallazgo"), datos)

    assert respuesta.status_code == 403
    assert not Publicacion.objects.exists()


def test_una_cuenta_suspendida_ni_siquiera_ve_los_asistentes(entrar, suspendida):
    cliente = entrar(suspendida)

    assert cliente.get(reverse("publicaciones:publicar_extravio")).status_code == 403
    assert cliente.get(reverse("publicaciones:publicar_hallazgo")).status_code == 403


def test_una_cuenta_suspendida_sigue_viendo_las_publicaciones(entrar, suspendida, beto):
    publicacion = hacer_publicacion(beto, descripcion="Se perdió en el centro")

    respuesta = entrar(suspendida).get(reverse("publicaciones:detalle", args=[publicacion.pk]))

    assert respuesta.status_code == 200


def test_una_cuenta_suspendida_no_puede_dar_de_alta_en_adopcion(entrar, suspendida):
    datos = {"especie": "perro", "fotos": [crear_imagen()]}

    respuesta = entrar(suspendida).post(reverse("publicaciones:alta_adopcion"), datos)

    assert respuesta.status_code == 403
    assert not Publicacion.objects.exists()
    assert not FichaAnimal.objects.exists()
