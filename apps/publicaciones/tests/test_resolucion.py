import pytest
from model_bakery import baker

from apps.cuentas.models import EstadoCuenta, Rol
from apps.fichas.models import FichaAnimal
from apps.mapa import capas
from apps.publicaciones import listados, resolucion
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

Tipo, Estado = Publicacion.Tipo, Publicacion.Estado

pytestmark = pytest.mark.django_db


@pytest.fixture
def moderadora(django_user_model):
    return django_user_model.objects.create_user(
        "mora@ejemplo.com",
        "Mora",
        "clave-de-prueba-1",
        estado_cuenta=EstadoCuenta.ACTIVA,
        rol=Rol.MODERADOR,
    )


@pytest.fixture
def ficha_de_ana(ana):
    return baker.make(FichaAnimal, especie="perro", responsable=ana)


def test_el_responsable_resuelve_el_caso_y_las_publicaciones_siguen_en_la_ficha(
    ana, beto, ficha_de_ana
):
    extravio = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=ficha_de_ana)
    hallazgo = hacer_publicacion(beto, tipo=Tipo.HALLAZGO, ficha=ficha_de_ana)

    resueltas = resolucion.resolver_caso(ficha_de_ana, ana)

    assert resueltas == 2
    for publicacion in (extravio, hallazgo):
        publicacion.refresh_from_db()
        assert publicacion.estado == Estado.RESUELTA
        assert publicacion.ficha_id == ficha_de_ana.pk


def test_solo_resuelve_extravios_y_hallazgos_vigentes(ana, ficha_de_ana):
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=ficha_de_ana)
    adopcion = hacer_publicacion(ana, tipo=Tipo.ADOPCION, ficha=ficha_de_ana)
    eliminada = hacer_publicacion(
        ana, tipo=Tipo.EXTRAVIO, ficha=ficha_de_ana, estado=Estado.ELIMINADA
    )

    resolucion.resolver_caso(ficha_de_ana, ana)

    adopcion.refresh_from_db()
    eliminada.refresh_from_db()
    assert adopcion.estado == Estado.VIGENTE
    assert eliminada.estado == Estado.ELIMINADA


def test_el_autor_del_hallazgo_tambien_puede_resolver(ana, beto, ficha_de_ana):
    hacer_publicacion(beto, tipo=Tipo.HALLAZGO, ficha=ficha_de_ana)

    assert resolucion.puede_resolver(beto, ficha_de_ana)


def test_sin_responsable_usuario_solo_un_moderador_resuelve(beto, moderadora):
    ficha = baker.make(FichaAnimal, especie="gato", responsable=None)
    hacer_publicacion(beto, tipo=Tipo.HALLAZGO, ficha=ficha)

    assert not resolucion.puede_resolver(beto, ficha)
    assert resolucion.puede_resolver(moderadora, ficha)


def test_sin_caso_abierto_no_hay_nada_que_resolver(ana, moderadora, ficha_de_ana):
    hacer_publicacion(ana, tipo=Tipo.ADOPCION, ficha=ficha_de_ana)

    assert not resolucion.puede_resolver(ana, ficha_de_ana)
    assert not resolucion.puede_resolver(moderadora, ficha_de_ana)


def test_sin_permiso_no_cambia_nada(ana, beto, ficha_de_ana):
    extravio = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=ficha_de_ana)

    with pytest.raises(PermissionError):
        resolucion.resolver_caso(ficha_de_ana, beto)

    extravio.refresh_from_db()
    assert extravio.estado == Estado.VIGENTE


def test_al_resolver_sale_del_listado_y_del_mapa_de_perdidos(ana, ficha_de_ana):
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=ficha_de_ana)

    resolucion.resolver_caso(ficha_de_ana, ana)

    assert not listados.perdidos().exists()
    assert not capas.vigentes().exists()
