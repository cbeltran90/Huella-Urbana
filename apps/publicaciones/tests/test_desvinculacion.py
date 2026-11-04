import pytest
from django.urls import reverse
from model_bakery import baker

from apps.cuentas.models import Rol
from apps.fichas.models import Coincidencia, FichaAnimal
from apps.publicaciones import vinculacion
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

pytestmark = pytest.mark.django_db


@pytest.fixture
def vinculada(ana, beto):
    """Publicación de Beto vinculada a la ficha de Ana (responsable)."""
    ficha = baker.make(FichaAnimal, especie="perro", responsable=ana)
    pub = hacer_publicacion(beto, tipo=Publicacion.Tipo.HALLAZGO, ficha=ficha)
    return pub, ficha


@pytest.fixture
def moderador(django_user_model):
    return django_user_model.objects.create_user(
        "mod@ejemplo.com", "Mod", "clave-de-prueba-1", rol=Rol.MODERADOR, estado_cuenta="activa"
    )


@pytest.fixture
def carla(django_user_model):
    return django_user_model.objects.create_user(
        "carla@ejemplo.com", "Carla", "clave-de-prueba-1", estado_cuenta="activa"
    )


@pytest.mark.parametrize("quien", ["ana", "beto", "moderador"])
def test_pueden_desvincular_autor_responsable_y_moderador(quien, vinculada, request):
    pub, ficha = vinculada
    usuario = request.getfixturevalue(quien)
    assert vinculacion.desvincular(pub, usuario) == ficha
    pub.refresh_from_db()
    assert pub.ficha is None


def test_un_tercero_no_puede_desvincular(vinculada, carla):
    pub, ficha = vinculada
    with pytest.raises(PermissionError):
        vinculacion.desvincular(pub, carla)
    pub.refresh_from_db()
    assert pub.ficha == ficha


def test_desvincular_marca_la_coincidencia_como_descartada(vinculada, beto):
    pub, ficha = vinculada
    baker.make(Coincidencia, publicacion=pub, ficha=ficha, elegida_por_autor=True)
    vinculacion.desvincular(pub, beto)
    c = Coincidencia.objects.get()
    assert not c.elegida_por_autor
    assert c.decision_responsable == Coincidencia.Decision.DESCARTADA


def test_el_rastro_de_la_ficha_se_actualiza(vinculada, beto):
    pub, ficha = vinculada
    assert list(ficha.publicaciones.all()) == [pub]
    vinculacion.desvincular(pub, beto)
    assert list(ficha.publicaciones.all()) == []


def test_una_publicacion_suelta_no_se_puede_desvincular(beto):
    pub = hacer_publicacion(beto, tipo=Publicacion.Tipo.HALLAZGO, ficha=None)
    assert not vinculacion.puede_desvincular(pub, beto)


def test_vista_pide_confirmacion_y_cancelar_no_cambia_nada(vinculada, entrar, beto):
    pub, ficha = vinculada
    url = reverse("publicaciones:desvincular", args=[pub.pk])
    assert entrar(beto).get(url).status_code == 200
    pub.refresh_from_db()
    assert pub.ficha == ficha


def test_vista_confirmar_desvincula(vinculada, entrar, beto):
    pub, _ = vinculada
    respuesta = entrar(beto).post(reverse("publicaciones:desvincular", args=[pub.pk]))
    assert respuesta.status_code == 302
    pub.refresh_from_db()
    assert pub.ficha is None


def test_vista_tercero_recibe_403(vinculada, entrar, carla):
    pub, _ = vinculada
    url = reverse("publicaciones:desvincular", args=[pub.pk])
    assert entrar(carla).post(url).status_code == 403


def test_el_detalle_muestra_el_boton_solo_a_quien_puede(vinculada, entrar, beto, carla):
    pub, _ = vinculada
    url = reverse("publicaciones:detalle", args=[pub.pk])
    assert "Desvincular de la ficha" in entrar(beto).get(url).content.decode()
    assert "Desvincular de la ficha" not in entrar(carla).get(url).content.decode()
