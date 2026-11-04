import pytest
from model_bakery import baker

from apps.cuentas.models import Rol
from apps.fichas.models import Coincidencia, FichaAnimal
from apps.publicaciones import vinculacion
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

pytestmark = pytest.mark.django_db


@pytest.fixture
def moderador(django_user_model):
    return django_user_model.objects.create_user(
        "mod@ejemplo.com", "Mod", "clave-de-prueba-1", rol=Rol.MODERADOR, estado_cuenta="activa"
    )


def test_decisores_con_responsable_es_solo_el_responsable(ana, moderador):
    ficha = baker.make(FichaAnimal, responsable=ana)
    assert vinculacion.decisores(ficha) == [ana]


def test_decisores_sin_responsable_son_el_cuidador_y_los_moderadores(beto, moderador):
    ficha = baker.make(FichaAnimal, responsable=None, cuidador=beto)
    assert vinculacion.decisores(ficha) == [beto, moderador]


def test_el_cuidador_puede_confirmar_un_extravio_contra_su_hallazgo(ana, beto):
    """Ana perdió al perro; Beto lo encontró y lo tiene. Decide Beto y sobrevive la ficha de Ana."""
    ficha_ana = baker.make(FichaAnimal, especie="perro", color="negro", responsable=ana)
    ficha_beto = baker.make(FichaAnimal, especie="perro", color="negro", cuidador=beto)
    pub_ana = hacer_publicacion(
        ana, tipo=Publicacion.Tipo.EXTRAVIO, ficha=ficha_ana, especie="perro", color="negro"
    )
    pub_beto = hacer_publicacion(
        beto, tipo=Publicacion.Tipo.HALLAZGO, ficha=ficha_beto, especie="perro", color="negro"
    )
    coincidencia = vinculacion.proponer_coincidencias(pub_ana)[0]
    vinculacion.vincular(pub_ana, ficha_beto, ana)

    vinculacion.responder(coincidencia, beto, confirmar=True)

    pub_ana.refresh_from_db()
    pub_beto.refresh_from_db()
    ficha_beto.refresh_from_db()
    ficha_ana.refresh_from_db()
    assert coincidencia.ficha == ficha_beto
    assert pub_ana.ficha == ficha_ana and pub_beto.ficha == ficha_ana
    assert ficha_beto.fusionada_en == ficha_ana
    assert ficha_ana.cuidador == beto
    coincidencia.refresh_from_db()
    assert coincidencia.decision_responsable == Coincidencia.Decision.CONFIRMADA


def test_un_moderador_puede_decidir(ana, beto, moderador):
    ficha = baker.make(FichaAnimal, especie="perro", responsable=None)
    pub = hacer_publicacion(beto, tipo=Publicacion.Tipo.EXTRAVIO, ficha=None, especie="perro")
    c = baker.make(Coincidencia, publicacion=pub, ficha=ficha)
    vinculacion.responder(c, moderador, confirmar=False)
    c.refresh_from_db()
    assert c.decision_responsable == Coincidencia.Decision.DESCARTADA
