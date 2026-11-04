import numpy as np
import pytest
from constance.test import override_config
from model_bakery import baker

from apps.fichas.comparacion import buscar_candidatas, contar_atributos
from apps.fichas.models import FichaAnimal
from apps.imagenes import vision
from apps.imagenes.models import Fotografia
from apps.publicaciones.models import Publicacion

pytestmark = pytest.mark.django_db
PUNTO = "SRID=4326;POINT(-68.3 -54.8)"


def _ficha(**campos):
    datos = {"especie": "perro", "tamano": "mediano", "raza": "", "color": "", **campos}
    return baker.make(FichaAnimal, **datos)


def _pub(ficha, tipo, autor=None, **campos):
    return baker.make(
        Publicacion,
        tipo=tipo,
        ficha=ficha,
        autor=autor,
        ubicacion=PUNTO,
        estado=Publicacion.Estado.VIGENTE,
        especie=ficha.especie,
        tamano=ficha.tamano,
        raza=ficha.raza,
        color=ficha.color,
        **campos,
    )


def _foto(ficha, vector):
    return baker.make(
        Fotografia, ficha=ficha, embedding=vision.a_bytes(np.array(vector, dtype=np.float32))
    )


def test_contar_atributos_ignora_vacios_y_mayusculas():
    ficha = _ficha(color="Negro", raza="")
    pub = baker.prepare(Publicacion, especie="perro", tamano="mediano", color="negro", raza="")
    assert contar_atributos(pub, ficha) == 3


def test_extravio_encuentra_hallazgo_con_dos_atributos():
    perdido = _ficha(color="negro")
    hallado = _ficha(color="negro")
    pub = _pub(perdido, Publicacion.Tipo.EXTRAVIO)
    _pub(hallado, Publicacion.Tipo.HALLAZGO)
    assert [c[0] for c in buscar_candidatas(pub)] == [hallado]


def test_no_propone_la_misma_ficha_ni_publicaciones_del_mismo_tipo():
    ficha = _ficha(color="negro")
    pub = _pub(ficha, Publicacion.Tipo.EXTRAVIO)
    otra = _ficha(color="negro")
    _pub(otra, Publicacion.Tipo.EXTRAVIO)
    assert buscar_candidatas(pub) == []


def test_otra_especie_no_es_candidata():
    pub = _pub(_ficha(color="negro"), Publicacion.Tipo.EXTRAVIO)
    gato = baker.make(FichaAnimal, especie="gato", tamano="mediano", color="negro")
    _pub(gato, Publicacion.Tipo.HALLAZGO)
    assert buscar_candidatas(pub) == []


@override_config(UMBRAL_SIMILITUD=0.8)
def test_similitud_alta_alcanza_aunque_coincida_un_solo_atributo():
    perdido = baker.make(FichaAnimal, especie="perro", tamano="chico", color="", raza="")
    hallado = baker.make(FichaAnimal, especie="perro", tamano="grande", color="", raza="")
    _foto(perdido, [1, 0, 0, 0])
    _foto(hallado, [1, 0, 0, 0])
    pub = _pub(perdido, Publicacion.Tipo.EXTRAVIO)
    _pub(hallado, Publicacion.Tipo.HALLAZGO)
    candidatas = buscar_candidatas(pub)
    assert len(candidatas) == 1 and candidatas[0][2] == pytest.approx(1.0)


def test_orden_por_similitud():
    perdido = _ficha(color="negro")
    _foto(perdido, [1, 0, 0, 0])
    cerca = _ficha(color="negro")
    lejos = _ficha(color="negro")
    _foto(cerca, [1, 0.1, 0, 0])
    _foto(lejos, [0, 1, 0, 0])
    pub = _pub(perdido, Publicacion.Tipo.EXTRAVIO)
    _pub(cerca, Publicacion.Tipo.HALLAZGO)
    _pub(lejos, Publicacion.Tipo.HALLAZGO)
    assert [c[0] for c in buscar_candidatas(pub)] == [cerca, lejos]
