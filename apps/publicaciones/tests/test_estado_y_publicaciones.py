import pytest
from model_bakery import baker

from apps.fichas.models import FichaAnimal
from apps.fichas.servicios import cambiar_estado
from apps.publicaciones import avisos, servicios
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

pytestmark = pytest.mark.django_db

Estado = FichaAnimal.Estado
Tipo = Publicacion.Tipo


@pytest.fixture(autouse=True)
def sin_avisos(monkeypatch):
    monkeypatch.setattr(avisos, "avisar_hogares_compatibles", lambda publicacion: 0)


def _vigentes(ficha):
    return ficha.publicaciones.filter(estado=Publicacion.Estado.VIGENTE)


def test_al_salir_de_adopcion_su_publicacion_pasa_a_resuelta(ana):
    ficha = baker.make(FichaAnimal, estado=Estado.EN_ADOPCION, cuidador=ana)
    adopcion = hacer_publicacion(ana, tipo=Tipo.ADOPCION, ficha=ficha)

    cambiar_estado(ficha, Estado.REGISTRADO, actor=None, cambios={"responsable": ana})

    adopcion.refresh_from_db()
    assert adopcion.estado == Publicacion.Estado.RESUELTA
    assert adopcion.ficha == ficha  # sigue vinculada


def test_al_salir_de_transito_su_publicacion_pasa_a_resuelta(ana):
    ficha = baker.make(FichaAnimal, estado=Estado.EN_TRANSITO, cuidador=ana)
    transito = hacer_publicacion(ana, tipo=Tipo.TRANSITO, ficha=ficha)

    cambiar_estado(ficha, Estado.EN_ADOPCION, actor=ana)

    transito.refresh_from_db()
    assert transito.estado == Publicacion.Estado.RESUELTA


def test_el_extravio_y_el_hallazgo_son_independientes_del_estado(ana):
    ficha = baker.make(FichaAnimal, estado=Estado.EN_ADOPCION, cuidador=ana)
    extravio = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=ficha)

    cambiar_estado(ficha, Estado.REGISTRADO, actor=None, cambios={"responsable": ana})

    extravio.refresh_from_db()
    assert extravio.estado == Publicacion.Estado.VIGENTE


def test_un_cambio_que_no_sale_de_adopcion_ni_de_transito_no_toca_publicaciones(ana):
    ficha = baker.make(FichaAnimal, estado=Estado.SIN_RESPONSABLE, cuidador=ana)
    hallazgo = hacer_publicacion(ana, tipo=Tipo.HALLAZGO, ficha=ficha)

    cambiar_estado(ficha, Estado.REGISTRADO, actor=None, cambios={"responsable": ana})

    hallazgo.refresh_from_db()
    assert hallazgo.estado == Publicacion.Estado.VIGENTE


def test_pasar_a_transito_y_publicar_deja_una_sola_vigente(ana, con_domicilio):
    ficha = baker.make(FichaAnimal, estado=Estado.EN_ADOPCION, cuidador=ana)
    hacer_publicacion(
        ana, tipo=Tipo.ADOPCION, ficha=ficha, descripcion="Cariñoso", telefono_visible="2901-1"
    )

    cambiar_estado(ficha, Estado.EN_TRANSITO, actor=ana)
    transito = servicios.publicar_transito_de_ficha(ficha, ana)

    assert list(_vigentes(ficha)) == [transito]
    assert transito.tipo == Tipo.TRANSITO
    assert transito.ubicacion.equals(con_domicilio)
    assert (transito.descripcion, transito.telefono_visible) == ("Cariñoso", "2901-1")


def test_el_relevo_vuelve_a_adopcion_con_una_sola_vigente(ana, con_domicilio):
    ficha = baker.make(FichaAnimal, estado=Estado.EN_TRANSITO, cuidador=ana)
    hacer_publicacion(ana, tipo=Tipo.TRANSITO, ficha=ficha)

    cambiar_estado(ficha, Estado.EN_ADOPCION, actor=ana)
    adopcion = servicios.publicar_adopcion_de_ficha(ficha, ana)

    assert list(_vigentes(ficha)) == [adopcion]
    assert adopcion.tipo == Tipo.ADOPCION


def test_publicar_en_transito_pide_que_la_ficha_este_en_transito(ana):
    ficha = baker.make(FichaAnimal, estado=Estado.EN_ADOPCION, cuidador=ana)

    with pytest.raises(ValueError, match="en tránsito"):
        servicios.publicar_transito_de_ficha(ficha, ana)


def test_publicar_en_transito_pide_el_hogar(ana):
    ficha = baker.make(FichaAnimal, estado=Estado.EN_TRANSITO, cuidador=None)

    with pytest.raises(ValueError, match="hogar"):
        servicios.publicar_transito_de_ficha(ficha, ana)
