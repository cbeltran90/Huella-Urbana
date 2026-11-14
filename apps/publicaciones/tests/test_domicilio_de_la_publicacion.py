import pytest
from django.contrib.gis.geos import Point
from model_bakery import baker

from apps.cuentas.models import Domicilio
from apps.cuentas.servicios import guardar_domicilio
from apps.fichas.models import FichaAnimal
from apps.publicaciones import avisos, servicios

pytestmark = pytest.mark.django_db

PUNTO = Point(-68.2999, -54.8011, srid=4326)
Estado = FichaAnimal.Estado


@pytest.fixture(autouse=True)
def sin_avisos(monkeypatch):
    monkeypatch.setattr(avisos, "avisar_hogares_compatibles", lambda publicacion: 0)


def test_el_extravio_queda_vinculado_al_domicilio_del_autor(ana):
    guardar_domicilio(ana, PUNTO)
    ficha = baker.make(FichaAnimal, responsable=ana, especie="perro")

    publicacion = servicios.publicar_extravio(ana, ficha=ficha, descripcion="Se perdió")

    domicilio = Domicilio.objects.get(usuario=ana)
    assert publicacion.domicilio == domicilio
    assert publicacion.ubicacion.equals(domicilio.ubicacion_desplazada)


def test_el_hallazgo_no_tiene_domicilio(ana):
    from .conftest import crear_imagen

    publicacion = servicios.publicar_hallazgo(
        ana,
        animal={"especie": "gato"},
        archivo=crear_imagen(),
        punto=PUNTO,
        estado_aparente="",
        descripcion="",
        tiene_consigo=False,
    )

    assert publicacion.domicilio is None


def test_la_adopcion_de_una_ficha_toma_el_domicilio_del_cuidador(ana):
    guardar_domicilio(ana, PUNTO)
    ficha = baker.make(FichaAnimal, estado=Estado.EN_ADOPCION, cuidador=ana)

    publicacion = servicios.publicar_adopcion_de_ficha(ficha, ana)

    assert publicacion.domicilio == Domicilio.objects.get(usuario=ana)


def test_el_punto_que_marca_un_moderador_no_tiene_domicilio(beto):
    ficha = baker.make(FichaAnimal, estado=Estado.EN_ADOPCION, cuidador=None)

    publicacion = servicios.publicar_adopcion_de_ficha(ficha, beto, punto=PUNTO)

    assert publicacion.domicilio is None


def test_si_se_elimina_el_domicilio_la_publicacion_conserva_su_punto(ana):
    guardar_domicilio(ana, PUNTO)
    ficha = baker.make(FichaAnimal, responsable=ana, especie="perro")
    publicacion = servicios.publicar_extravio(ana, ficha=ficha, descripcion="")
    punto = publicacion.ubicacion.clone()

    Domicilio.objects.filter(usuario=ana).delete()

    publicacion.refresh_from_db()
    assert publicacion.domicilio is None
    assert publicacion.ubicacion.equals(punto)
