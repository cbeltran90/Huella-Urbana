import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from model_bakery import baker

from apps.fichas.comparacion import buscar_candidatas
from apps.fichas.models import FichaAnimal
from apps.fichas.servicios import crear_ficha_sin_responsable
from apps.publicaciones.models import Publicacion

pytestmark = pytest.mark.django_db


def test_deja_a_nina_con_extravio_y_a_pipo_privado():
    call_command("cargar_demo_extravio")

    nina = FichaAnimal.objects.get(nombre="Nina")
    pipo = FichaAnimal.objects.get(nombre="Pipo")
    assert Publicacion.objects.filter(ficha=nina, tipo=Publicacion.Tipo.EXTRAVIO).count() == 1
    assert not Publicacion.objects.filter(ficha=pipo).exists()
    assert pipo.es_privada
    assert get_user_model().objects.filter(email="camila@demo.huella.test").exists()


def test_se_puede_correr_dos_veces_sin_duplicar():
    call_command("cargar_demo_extravio")
    call_command("cargar_demo_extravio")

    assert FichaAnimal.objects.count() == 2
    assert Publicacion.objects.count() == 1
    assert get_user_model().objects.count() == 3


def test_el_hallazgo_de_camila_sugiere_a_nina_y_luego_a_pipo():
    call_command("cargar_demo_extravio")
    camila = get_user_model().objects.get(email="camila@demo.huella.test")
    ficha = crear_ficha_sin_responsable(
        {"especie": "gato", "tamano": "mediano", "raza": "mestizo", "color": "gris"}
    )
    hallazgo = baker.make(
        Publicacion,
        tipo=Publicacion.Tipo.HALLAZGO,
        autor=camila,
        ficha=ficha,
        ubicacion="SRID=4326;POINT(-68.2 -54.8)",
        especie="gato",
        tamano="mediano",
        raza="mestizo",
        color="gris",
    )

    candidatas = buscar_candidatas(hallazgo)

    assert [(c[0].nombre, c[1]) for c in candidatas] == [("Nina", 4), ("Pipo", 3)]
