import pytest
from django.core.management import call_command

from apps.fichas.models import FichaAnimal
from apps.imagenes.models import Fotografia

from .conftest import crear_imagen

pytestmark = pytest.mark.django_db


def test_el_comando_agrega_la_foto_indicada(tmp_path):
    ruta = tmp_path / "gato.jpg"
    ruta.write_bytes(crear_imagen().read())

    call_command("cargar_demo_extravio", foto_nina=str(ruta))

    nina = FichaAnimal.objects.get(nombre="Nina")
    assert Fotografia.objects.filter(ficha=nina).count() == 1


def test_correrlo_otra_vez_no_repite_la_foto(tmp_path):
    ruta = tmp_path / "gato.jpg"
    ruta.write_bytes(crear_imagen().read())

    call_command("cargar_demo_extravio", foto_nina=str(ruta))
    call_command("cargar_demo_extravio", foto_nina=str(ruta))

    assert Fotografia.objects.count() == 1
