import pytest
from django.urls import reverse
from model_bakery import baker

from apps.fichas.models import Coincidencia, FichaAnimal
from apps.publicaciones import vinculacion
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

pytestmark = pytest.mark.django_db


@pytest.fixture
def escenario(ana, beto):
    """Beto halló un animal; Ana es responsable de una ficha parecida."""
    ficha_ana = baker.make(
        FichaAnimal, especie="perro", tamano="mediano", color="negro", responsable=ana
    )
    hallada = baker.make(FichaAnimal, especie="perro", tamano="mediano", color="negro")
    hacer_publicacion(
        ana,
        tipo=Publicacion.Tipo.EXTRAVIO,
        ficha=ficha_ana,
        especie="perro",
        tamano="mediano",
        color="negro",
    )
    pub = hacer_publicacion(
        beto,
        tipo=Publicacion.Tipo.HALLAZGO,
        ficha=hallada,
        especie="perro",
        tamano="mediano",
        color="negro",
    )
    return pub, ficha_ana, hallada


def test_proponer_guarda_candidatas(escenario):
    pub, ficha_ana, _ = escenario
    resultado = vinculacion.proponer_coincidencias(pub)
    assert [c.ficha for c in resultado] == [ficha_ana]
    assert resultado[0].decision_responsable == Coincidencia.Decision.PENDIENTE


def test_proponer_dos_veces_no_duplica(escenario):
    pub, _, _ = escenario
    vinculacion.proponer_coincidencias(pub)
    vinculacion.proponer_coincidencias(pub)
    assert Coincidencia.objects.count() == 1


def test_vincular_marca_elegida(escenario, beto):
    pub, ficha_ana, _ = escenario
    vinculacion.proponer_coincidencias(pub)
    c = vinculacion.vincular(pub, ficha_ana, beto)
    assert c.elegida_por_autor


def test_vincular_solo_el_autor(escenario, ana):
    pub, ficha_ana, _ = escenario
    vinculacion.proponer_coincidencias(pub)
    with pytest.raises(PermissionError):
        vinculacion.vincular(pub, ficha_ana, ana)


def test_confirmar_fusiona_y_mueve_la_publicacion(escenario, ana, beto):
    pub, ficha_ana, hallada = escenario
    c = vinculacion.proponer_coincidencias(pub)[0]
    vinculacion.vincular(pub, ficha_ana, beto)
    vinculacion.responder(c, ana, confirmar=True)
    pub.refresh_from_db()
    hallada.refresh_from_db()
    assert pub.ficha == ficha_ana
    assert hallada.fusionada_en == ficha_ana


def test_descartar_deja_todo_igual(escenario, ana, beto):
    pub, ficha_ana, hallada = escenario
    c = vinculacion.proponer_coincidencias(pub)[0]
    vinculacion.vincular(pub, ficha_ana, beto)
    vinculacion.responder(c, ana, confirmar=False)
    pub.refresh_from_db()
    c.refresh_from_db()
    assert pub.ficha == hallada
    assert c.decision_responsable == Coincidencia.Decision.DESCARTADA


def test_responder_solo_el_responsable(escenario, beto):
    pub, ficha_ana, _ = escenario
    c = vinculacion.proponer_coincidencias(pub)[0]
    with pytest.raises(PermissionError):
        vinculacion.responder(c, beto, confirmar=True)


def test_vista_candidatas_lista_y_elige(escenario, entrar, beto):
    pub, ficha_ana, _ = escenario
    vinculacion.proponer_coincidencias(pub)
    cliente = entrar(beto)
    url = reverse("publicaciones:candidatas", args=[pub.pk])
    assert cliente.get(url).status_code == 200
    respuesta = cliente.post(url, {"ficha": ficha_ana.pk})
    assert respuesta.status_code == 302
    assert Coincidencia.objects.get().elegida_por_autor


def test_vista_ninguna_corresponde(escenario, entrar, beto):
    pub, _, _ = escenario
    vinculacion.proponer_coincidencias(pub)
    respuesta = entrar(beto).post(reverse("publicaciones:candidatas", args=[pub.pk]))
    assert respuesta.status_code == 302
    assert not Coincidencia.objects.get().elegida_por_autor


def test_vista_candidatas_ajena_da_404(escenario, entrar, ana):
    pub, _, _ = escenario
    assert entrar(ana).get(reverse("publicaciones:candidatas", args=[pub.pk])).status_code == 404


def test_vista_responder_confirma(escenario, entrar, ana, beto):
    pub, ficha_ana, _ = escenario
    c = vinculacion.proponer_coincidencias(pub)[0]
    vinculacion.vincular(pub, ficha_ana, beto)
    url = reverse("publicaciones:responder_coincidencia", args=[c.pk])
    assert entrar(ana).post(url, {"accion": "confirmar"}).status_code == 302
    c.refresh_from_db()
    assert c.decision_responsable == Coincidencia.Decision.CONFIRMADA
