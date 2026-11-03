import pytest
from django.contrib.gis.geos import Point
from model_bakery import baker

from apps.fichas.models import FichaAnimal
from apps.imagenes.models import Fotografia
from apps.imagenes.procesamiento import ImagenInvalida
from apps.publicaciones import servicios, ubicacion
from apps.publicaciones.models import Publicacion

from .conftest import crear_imagen

pytestmark = pytest.mark.django_db

ANIMAL = {
    "nombre": "Firulais",
    "especie": "perro",
    "tamano": "mediano",
    "raza": "",
    "color": "negro",
}


def test_publica_el_extravio_de_una_ficha_propia(ana, con_domicilio):
    ficha = baker.make(FichaAnimal, responsable=ana, especie="gato", color="gris")

    publicacion = servicios.publicar_extravio(ana, ficha=ficha, descripcion="Se escapó")

    assert publicacion.tipo == Publicacion.Tipo.EXTRAVIO
    assert publicacion.estado == Publicacion.Estado.VIGENTE
    assert publicacion.autor == ana
    assert publicacion.ficha == ficha
    assert publicacion.especie == "gato"
    assert publicacion.color == "gris"
    assert publicacion.ubicacion.equals_exact(con_domicilio, 1e-9)
    assert FichaAnimal.objects.count() == 1


def test_con_un_animal_nuevo_crea_la_ficha_y_guarda_la_foto(ana, con_domicilio):
    publicacion = servicios.publicar_extravio(ana, animal=ANIMAL, archivo=crear_imagen())

    ficha = publicacion.ficha
    assert ficha.responsable == ana
    assert ficha.estado == FichaAnimal.Estado.REGISTRADO
    assert ficha.especie == "perro"
    assert Fotografia.objects.get().ficha == ficha


def test_una_ficha_propia_puede_publicarse_sin_foto(ana, con_domicilio):
    ficha = baker.make(FichaAnimal, responsable=ana)

    servicios.publicar_extravio(ana, ficha=ficha)

    assert not Fotografia.objects.exists()


def test_un_animal_nuevo_sin_foto_no_se_publica(ana, con_domicilio):
    with pytest.raises(ValueError):
        servicios.publicar_extravio(ana, animal=ANIMAL)

    assert not FichaAnimal.objects.exists()


def test_sin_domicilio_se_usa_el_punto_indicado_pero_se_publica_el_desplazado(ana, monkeypatch):
    exacto = Point(-68.3030, -54.8019, srid=4326)
    desplazado = Point(-68.3031, -54.8020, srid=4326)
    guardados = []
    monkeypatch.setattr(ubicacion, "punto_de_domicilio", lambda usuario: None)
    monkeypatch.setattr(
        ubicacion,
        "registrar_domicilio",
        lambda usuario, punto: guardados.append(punto) or desplazado,
    )
    ficha = baker.make(FichaAnimal, responsable=ana)

    publicacion = servicios.publicar_extravio(ana, ficha=ficha, punto=exacto)

    assert guardados == [exacto]
    assert publicacion.ubicacion.equals_exact(desplazado, 1e-9)
    assert not publicacion.ubicacion.equals_exact(exacto, 1e-9)


def test_sin_domicilio_ni_punto_no_se_publica(ana, monkeypatch):
    monkeypatch.setattr(ubicacion, "punto_de_domicilio", lambda usuario: None)
    ficha = baker.make(FichaAnimal, responsable=ana)

    with pytest.raises(ValueError):
        servicios.publicar_extravio(ana, ficha=ficha)


def test_una_foto_invalida_no_deja_nada_a_medias(ana, con_domicilio):
    from django.core.files.uploadedfile import SimpleUploadedFile

    with pytest.raises(ImagenInvalida):
        servicios.publicar_extravio(
            ana, animal=ANIMAL, archivo=SimpleUploadedFile("a.jpg", b"no es una imagen")
        )

    assert not FichaAnimal.objects.exists()
    assert not Publicacion.objects.exists()
