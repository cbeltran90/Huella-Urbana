import pytest
from django.urls import reverse
from model_bakery import baker

from apps.fichas.models import FichaAnimal
from apps.publicaciones import vinculacion
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

pytestmark = pytest.mark.django_db

Tipo = Publicacion.Tipo


def test_el_detalle_muestra_quien_publico_la_ficha_y_el_mapa(entrar, ana):
    ficha = baker.make(FichaAnimal, responsable=ana, especie="gato", es_privada=False)
    publicacion = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=ficha)

    contenido = (
        entrar(ana).get(reverse("publicaciones:detalle", args=[publicacion.pk])).content.decode()
    )

    assert "Ana" in contenido
    assert reverse("fichas:detalle", args=[ficha.pk]) in contenido
    assert 'id="mapa-publicacion"' in contenido


def test_la_ficha_privada_no_se_enlaza_a_quien_no_puede_verla(entrar, ana, beto):
    ficha = baker.make(FichaAnimal, responsable=ana, especie="gato", es_privada=True)
    publicacion = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=ficha)

    contenido = (
        entrar(beto).get(reverse("publicaciones:detalle", args=[publicacion.pk])).content.decode()
    )

    assert reverse("fichas:detalle", args=[ficha.pk]) not in contenido
    assert "ficha privada" in contenido


def test_el_autor_crea_la_ficha_de_su_extravio_suelto(entrar, ana):
    publicacion = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=None, especie="perro")

    respuesta = entrar(ana).post(reverse("publicaciones:crear_ficha", args=[publicacion.pk]))

    publicacion.refresh_from_db()
    ficha = publicacion.ficha
    assert respuesta.status_code == 302
    assert ficha.responsable == ana
    assert ficha.estado == FichaAnimal.Estado.REGISTRADO
    assert ficha.especie == "perro"


def test_el_hallazgo_suelto_crea_una_ficha_sin_responsable(ana):
    publicacion = hacer_publicacion(ana, tipo=Tipo.HALLAZGO, ficha=None, especie="gato")

    ficha = vinculacion.crear_ficha_desde_publicacion(publicacion, ana)

    assert ficha.estado == FichaAnimal.Estado.SIN_RESPONSABLE
    assert ficha.responsable is None


def test_un_tercero_no_puede_crear_la_ficha(entrar, ana, beto):
    publicacion = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=None)

    respuesta = entrar(beto).post(reverse("publicaciones:crear_ficha", args=[publicacion.pk]))

    assert respuesta.status_code == 403
    publicacion.refresh_from_db()
    assert publicacion.ficha is None


def test_una_publicacion_con_ficha_no_ofrece_crear_otra(ana):
    ficha = baker.make(FichaAnimal, responsable=ana, especie="gato")
    publicacion = hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=ficha)

    assert not vinculacion.puede_crear_ficha(publicacion, ana)


def test_una_publicacion_de_adopcion_suelta_no_crea_ficha(ana):
    publicacion = hacer_publicacion(ana, tipo=Tipo.ADOPCION, ficha=None)

    assert not vinculacion.puede_crear_ficha(publicacion, ana)
