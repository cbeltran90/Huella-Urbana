import pytest
from django.utils import timezone
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


@pytest.fixture
def ficha_hallada_por_beto(beto):
    return baker.make(
        FichaAnimal,
        especie="perro",
        estado=FichaAnimal.Estado.SIN_RESPONSABLE,
        responsable=None,
        cuidador=beto,
        sin_responsable_desde=timezone.localdate(),
    )


def test_quien_lo_tiene_a_cargo_confirma_al_dueno_transicion_4(ana, beto, ficha_hallada_por_beto):
    ficha = ficha_hallada_por_beto
    hallazgo = hacer_publicacion(beto, tipo=Tipo.HALLAZGO, ficha=ficha)
    extravio = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=ficha)

    resolucion.confirmar_dueno(ficha, extravio, beto)

    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.REGISTRADO
    assert ficha.responsable == ana
    assert ficha.cuidador is None and ficha.sin_responsable_desde is None
    for publicacion in (hallazgo, extravio):
        publicacion.refresh_from_db()
        assert publicacion.estado == Estado.RESUELTA


def test_un_moderador_tambien_confirma_al_dueno(ana, moderadora, ficha_hallada_por_beto):
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=ficha_hallada_por_beto)

    assert resolucion.puede_confirmar_dueno(moderadora, ficha_hallada_por_beto)


def test_quien_reclama_no_puede_confirmarse_a_si_mismo(ana, ficha_hallada_por_beto):
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=ficha_hallada_por_beto)

    assert not resolucion.puede_confirmar_dueno(ana, ficha_hallada_por_beto)


def test_sin_extravio_vinculado_no_hay_dueno_para_confirmar(beto, ficha_hallada_por_beto):
    hacer_publicacion(beto, tipo=Tipo.HALLAZGO, ficha=ficha_hallada_por_beto)

    assert not resolucion.puede_confirmar_dueno(beto, ficha_hallada_por_beto)


def test_un_extravio_de_otra_ficha_no_sirve(ana, beto, ficha_hallada_por_beto):
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=ficha_hallada_por_beto)
    ajeno = hacer_publicacion(
        ana, tipo=Tipo.EXTRAVIO, ficha=baker.make(FichaAnimal, especie="gato")
    )

    with pytest.raises(ValueError):
        resolucion.confirmar_dueno(ficha_hallada_por_beto, ajeno, beto)


@pytest.mark.parametrize("tipo", [Tipo.ADOPCION, Tipo.TRANSITO])
def test_adopcion_y_transito_se_retiran_con_la_ficha(ana, tipo):
    publicacion = hacer_publicacion(ana, tipo=tipo)

    assert resolucion.como_se_retira(publicacion, ana) == "ficha"


def test_un_extravio_propio_se_retira_resolviendo_el_caso(ana):
    ficha = baker.make(FichaAnimal, especie="perro", responsable=ana)
    extravio = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=ficha)

    assert resolucion.como_se_retira(extravio, ana) == "resolver"


def test_un_hallazgo_en_una_ficha_sin_responsable_lo_cierra_un_moderador(ana):
    ficha = baker.make(FichaAnimal, especie="perro", responsable=None)
    hallazgo = hacer_publicacion(ana, tipo=Tipo.HALLAZGO, ficha=ficha)

    assert resolucion.como_se_retira(hallazgo, ana) == "moderador"


def test_un_avistamiento_no_ofrece_retiro(ana):
    avistamiento = hacer_publicacion(ana, tipo=Tipo.SILVESTRE)

    assert resolucion.como_se_retira(avistamiento, ana) is None
