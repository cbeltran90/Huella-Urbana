import pytest
from django.contrib.gis.geos import Point
from model_bakery import baker

from apps.fichas.models import FichaAnimal
from apps.publicaciones import avisos, servicios, ubicacion
from apps.publicaciones.models import Publicacion

from .conftest import DOMICILIO, hacer_publicacion

pytestmark = pytest.mark.django_db

PUNTO = Point(-68.31, -54.81, srid=4326)
EXACTO = Point(-68.2999, -54.8011, srid=4326)  # el del hallazgo: no puede salir en la adopción


def _ficha(cuidador=None, **campos):
    datos = {
        "estado": FichaAnimal.Estado.EN_ADOPCION,
        "especie": "gato",
        "tamano": "pequeno",
        "color": "gris",
        "cuidador": cuidador,
        **campos,
    }
    return baker.make(FichaAnimal, **datos)


@pytest.fixture
def avisados(monkeypatch):
    """Anota las publicaciones por las que se avisó a los hogares."""
    llamadas = []
    monkeypatch.setattr(avisos, "avisar_hogares_compatibles", llamadas.append)
    return llamadas


def test_crea_una_sola_publicacion_de_adopcion_vigente(ana, con_domicilio, avisados):
    ficha = _ficha(cuidador=ana)

    publicacion = servicios.publicar_adopcion_de_ficha(ficha, ana, descripcion="Cariñoso")

    assert Publicacion.objects.filter(ficha=ficha).count() == 1
    assert publicacion.tipo == Publicacion.Tipo.ADOPCION
    assert publicacion.estado == Publicacion.Estado.VIGENTE
    assert publicacion.autor == ana and publicacion.descripcion == "Cariñoso"
    assert (publicacion.especie, publicacion.tamano, publicacion.color) == (
        "gato",
        "pequeno",
        "gris",
    )


def test_la_ubicacion_publicada_es_la_desplazada_del_domicilio(ana, con_domicilio, avisados):
    publicacion = servicios.publicar_adopcion_de_ficha(_ficha(cuidador=ana), ana)

    assert publicacion.ubicacion.equals(DOMICILIO)
    assert publicacion.ubicacion_desplazada is None


def test_sin_domicilio_se_usa_y_se_registra_el_punto(ana, monkeypatch, avisados):
    registrados = []
    monkeypatch.setattr(ubicacion, "punto_de_domicilio", lambda usuario: None)
    monkeypatch.setattr(
        ubicacion,
        "registrar_domicilio",
        lambda usuario, punto: registrados.append(usuario) or punto,
    )

    publicacion = servicios.publicar_adopcion_de_ficha(_ficha(cuidador=ana), ana, punto=PUNTO)

    assert publicacion.ubicacion.equals(PUNTO)
    assert registrados == [ana]


def test_sin_domicilio_ni_punto_se_pide_la_ubicacion(ana, monkeypatch, avisados):
    monkeypatch.setattr(ubicacion, "punto_de_domicilio", lambda usuario: None)

    with pytest.raises(ValueError, match="ubicación"):
        servicios.publicar_adopcion_de_ficha(_ficha(cuidador=ana), ana)

    assert not Publicacion.objects.exists()


def test_sin_usuario_a_cargo_el_punto_va_en_la_ubicacion_desplazada(beto, avisados):
    moderador = beto
    publicacion = servicios.publicar_adopcion_de_ficha(_ficha(), moderador, punto=PUNTO)

    assert publicacion.ubicacion.equals(PUNTO)
    assert publicacion.ubicacion_desplazada.equals(PUNTO)
    assert publicacion.autor == moderador


def test_sin_usuario_a_cargo_ni_punto_se_pide_la_ubicacion(beto, avisados):
    with pytest.raises(ValueError, match="ubicación"):
        servicios.publicar_adopcion_de_ficha(_ficha(), beto)


def test_la_ubicacion_exacta_del_hallazgo_no_se_copia(ana, beto, con_domicilio, avisados):
    ficha = _ficha(cuidador=ana)
    hallazgo = hacer_publicacion(
        beto, tipo=Publicacion.Tipo.HALLAZGO, ficha=ficha, ubicacion=EXACTO
    )

    publicacion = servicios.publicar_adopcion_de_ficha(ficha, ana)

    assert not publicacion.ubicacion.equals(EXACTO)
    hallazgo.refresh_from_db()
    assert hallazgo.ubicacion.equals(EXACTO)


def test_el_hallazgo_vigente_queda_resuelto_y_vinculado(ana, beto, con_domicilio, avisados):
    ficha = _ficha(cuidador=ana)
    hallazgo = hacer_publicacion(beto, tipo=Publicacion.Tipo.HALLAZGO, ficha=ficha)

    servicios.publicar_adopcion_de_ficha(ficha, ana)

    hallazgo.refresh_from_db()
    assert hallazgo.estado == Publicacion.Estado.RESUELTA
    assert hallazgo.ficha == ficha


def test_la_publicacion_de_adopcion_anterior_se_resuelve(ana, con_domicilio, avisados):
    ficha = _ficha(cuidador=ana)
    vieja = hacer_publicacion(ana, tipo=Publicacion.Tipo.TRANSITO, ficha=ficha)

    servicios.publicar_adopcion_de_ficha(ficha, ana)

    vieja.refresh_from_db()
    assert vieja.estado == Publicacion.Estado.RESUELTA
    vigentes = ficha.publicaciones.filter(estado=Publicacion.Estado.VIGENTE)
    assert vigentes.count() == 1


def test_avisa_a_los_hogares_despues_de_guardar(ana, con_domicilio, avisados):
    publicacion = servicios.publicar_adopcion_de_ficha(_ficha(cuidador=ana), ana)

    assert avisados == [publicacion]


def test_si_el_aviso_falla_la_publicacion_queda(ana, con_domicilio, monkeypatch):
    def falla(publicacion):
        raise RuntimeError("caído")

    monkeypatch.setattr(avisos, "avisar_hogares_compatibles", falla)

    publicacion = servicios.publicar_adopcion_de_ficha(_ficha(cuidador=ana), ana)

    assert Publicacion.objects.filter(pk=publicacion.pk).exists()


@pytest.mark.parametrize(
    "estado", [FichaAnimal.Estado.REGISTRADO, FichaAnimal.Estado.SIN_RESPONSABLE]
)
def test_la_ficha_tiene_que_estar_en_adopcion(ana, con_domicilio, avisados, estado):
    ficha = _ficha(cuidador=ana, estado=estado)

    with pytest.raises(ValueError, match="en adopción"):
        servicios.publicar_adopcion_de_ficha(ficha, ana)

    assert not Publicacion.objects.exists()
