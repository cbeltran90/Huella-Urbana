import pytest
from model_bakery import baker

from apps.cuentas import eliminacion as eliminacion_cuenta
from apps.fichas.models import Coincidencia, FichaAnimal
from apps.publicaciones import vinculacion
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

pytestmark = pytest.mark.django_db


def test_las_publicaciones_vigentes_pasan_a_resueltas_sin_autor(ana):
    pub = hacer_publicacion(ana, tipo=Publicacion.Tipo.HALLAZGO, ficha=None)
    antes = (pub.tipo, pub.ubicacion, pub.fecha)

    eliminacion_cuenta.eliminar_cuenta(ana)

    pub.refresh_from_db()
    assert pub.autor is None
    assert pub.estado == Publicacion.Estado.RESUELTA
    assert (pub.tipo, pub.ubicacion, pub.fecha) == antes


def test_se_borran_la_descripcion_y_el_telefono_de_todas_sus_publicaciones(ana):
    vigente = hacer_publicacion(
        ana, ficha=None, descripcion="Vivo en la calle X", telefono_visible="2901-111"
    )
    resuelta = hacer_publicacion(
        ana,
        ficha=None,
        estado=Publicacion.Estado.RESUELTA,
        descripcion="Texto",
        telefono_visible="2901-222",
    )

    eliminacion_cuenta.eliminar_cuenta(ana)

    for pub in (vigente, resuelta):
        pub.refresh_from_db()
        assert pub.autor is None and pub.descripcion == "" and pub.telefono_visible == ""
    assert Publicacion.objects.count() == 2  # se conserva la cantidad


def test_no_se_tocan_las_publicaciones_de_otras_personas(ana, beto):
    ajena = hacer_publicacion(beto, ficha=None, descripcion="Mía")

    eliminacion_cuenta.eliminar_cuenta(ana)

    ajena.refresh_from_db()
    assert ajena.autor == beto and ajena.descripcion == "Mía"
    assert ajena.estado == Publicacion.Estado.VIGENTE


def test_las_coincidencias_pendientes_de_sus_publicaciones_se_descartan(ana, beto):
    ficha = baker.make(FichaAnimal, responsable=beto)
    pub = hacer_publicacion(ana, tipo=Publicacion.Tipo.HALLAZGO, ficha=None)
    coincidencia = baker.make(Coincidencia, publicacion=pub, ficha=ficha, elegida_por_autor=True)

    eliminacion_cuenta.eliminar_cuenta(ana)

    coincidencia.refresh_from_db()
    assert coincidencia.decision_responsable == Coincidencia.Decision.DESCARTADA
    assert not vinculacion.pendientes_para(beto).exists()


def test_la_publicacion_de_una_ficha_borrada_queda_suelta_y_conservada(ana):
    ficha = baker.make(FichaAnimal, responsable=ana, estado=FichaAnimal.Estado.REGISTRADO)
    pub = hacer_publicacion(ana, tipo=Publicacion.Tipo.EXTRAVIO, ficha=ficha)

    eliminacion_cuenta.eliminar_cuenta(ana)

    pub.refresh_from_db()
    assert not FichaAnimal.objects.filter(pk=ficha.pk).exists()
    assert pub.ficha is None and pub.autor is None


def test_confirmar_una_coincidencia_de_una_publicacion_sin_autor_no_falla(ana, beto):
    ficha = baker.make(FichaAnimal, responsable=beto)
    propia = baker.make(FichaAnimal, responsable=None)  # la ficha que crea todo hallazgo
    pub = hacer_publicacion(ana, tipo=Publicacion.Tipo.HALLAZGO, ficha=propia)
    coincidencia = baker.make(Coincidencia, publicacion=pub, ficha=ficha, elegida_por_autor=True)
    Publicacion.objects.filter(pk=pub.pk).update(autor=None)
    coincidencia.refresh_from_db()

    vinculacion.responder(coincidencia, beto, confirmar=True)

    pub.refresh_from_db()
    assert pub.ficha == ficha
