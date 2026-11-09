import pytest
from django.urls import reverse
from model_bakery import baker

from apps.fichas.models import FichaAnimal
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

Tipo, Estado = Publicacion.Tipo, Publicacion.Estado

pytestmark = pytest.mark.django_db


@pytest.fixture
def caso_de_ana(ana):
    ficha = baker.make(FichaAnimal, especie="perro", responsable=ana)
    extravio = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=ficha)
    return ficha, extravio


def _resolver(ficha):
    return reverse("publicaciones:resolver_caso", args=[ficha.pk])


def test_el_responsable_ve_el_boton_en_su_ficha(entrar, ana, caso_de_ana):
    ficha, _ = caso_de_ana

    html = entrar(ana).get(reverse("fichas:detalle", args=[ficha.pk])).content.decode()

    assert _resolver(ficha) in html


def test_quien_no_puede_resolver_no_ve_el_boton(entrar, beto, caso_de_ana):
    ficha, _ = caso_de_ana
    ficha.es_privada = False
    ficha.save(update_fields=["es_privada"])

    html = entrar(beto).get(reverse("fichas:detalle", args=[ficha.pk])).content.decode()

    assert _resolver(ficha) not in html


def test_get_pide_confirmacion_sin_cambiar_nada(entrar, ana, caso_de_ana):
    ficha, extravio = caso_de_ana

    respuesta = entrar(ana).get(_resolver(ficha))

    assert "¿Cerrar el caso de extravío?" in respuesta.content.decode()
    extravio.refresh_from_db()
    assert extravio.estado == Estado.VIGENTE


def test_al_confirmar_resuelve_y_vuelve_a_la_ficha(entrar, ana, caso_de_ana):
    ficha, extravio = caso_de_ana

    respuesta = entrar(ana).post(_resolver(ficha))

    assert respuesta.url == reverse("fichas:detalle", args=[ficha.pk])
    extravio.refresh_from_db()
    assert extravio.estado == Estado.RESUELTA


def test_sin_permiso_da_403_y_no_cambia_nada(entrar, beto, caso_de_ana):
    ficha, extravio = caso_de_ana

    assert entrar(beto).post(_resolver(ficha)).status_code == 403
    extravio.refresh_from_db()
    assert extravio.estado == Estado.VIGENTE


def test_quien_lo_tiene_a_cargo_confirma_y_termina_en_el_listado(entrar, ana, beto):
    ficha = baker.make(
        FichaAnimal,
        especie="perro",
        estado=FichaAnimal.Estado.SIN_RESPONSABLE,
        responsable=None,
        cuidador=beto,
    )
    extravio = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=ficha)
    cliente = entrar(beto)
    url = reverse("publicaciones:confirmar_dueno", args=[extravio.pk])

    html = cliente.get(reverse("fichas:detalle", args=[ficha.pk])).content.decode()
    respuesta = cliente.post(url)

    assert url in html
    assert respuesta.url == reverse("publicaciones:perdidos")
    ficha.refresh_from_db()
    assert ficha.responsable == ana


def test_quien_reclama_no_ve_la_opcion(entrar, ana, beto):
    ficha = baker.make(
        FichaAnimal,
        especie="perro",
        estado=FichaAnimal.Estado.SIN_RESPONSABLE,
        responsable=None,
        cuidador=beto,
        es_privada=False,
    )
    extravio = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=ficha)

    html = entrar(ana).get(reverse("fichas:detalle", args=[ficha.pk])).content.decode()

    assert reverse("publicaciones:confirmar_dueno", args=[extravio.pk]) not in html
