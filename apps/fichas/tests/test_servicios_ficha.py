import pytest
from model_bakery import baker

from apps.fichas import servicios
from apps.fichas.models import FichaAnimal

Estado = FichaAnimal.Estado

pytestmark = pytest.mark.django_db


def test_el_alta_crea_una_ficha_registrada_privada_y_a_nombre_del_usuario(ana):
    ficha = servicios.crear_ficha(ana, {"especie": "perro", "nombre": "Firulais"})

    assert ficha.pk is not None
    assert ficha.responsable == ana
    assert ficha.estado == Estado.REGISTRADO
    assert ficha.es_privada is True
    assert ficha.cuidador is None


def test_el_alta_ignora_los_campos_que_no_son_editables(ana):
    datos = {"especie": "gato", "estado": Estado.EN_ADOPCION, "es_privada": False}

    ficha = servicios.crear_ficha(ana, datos)

    assert ficha.estado == Estado.REGISTRADO
    assert ficha.es_privada is True


def test_la_edicion_cambia_solo_los_campos_editables(ana, beto):
    ficha = baker.make(
        FichaAnimal, responsable=ana, nombre="Viejo", estado=Estado.REGISTRADO, especie="perro"
    )
    datos = {"nombre": "Nuevo", "estado": Estado.EN_TRANSITO, "responsable": beto}

    servicios.editar_ficha(ficha, datos)

    ficha.refresh_from_db()
    assert ficha.nombre == "Nuevo"
    assert ficha.estado == Estado.REGISTRADO
    assert ficha.responsable == ana


def test_la_baja_borra_la_ficha(ana):
    ficha = baker.make(FichaAnimal, responsable=ana)

    servicios.dar_de_baja(ficha)

    assert not FichaAnimal.objects.filter(pk=ficha.pk).exists()
