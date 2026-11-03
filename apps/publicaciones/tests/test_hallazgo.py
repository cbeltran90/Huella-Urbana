import pytest
from constance.test import override_config
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from apps.fichas.models import FichaAnimal
from apps.imagenes.models import Fotografia
from apps.imagenes.procesamiento import ImagenInvalida
from apps.publicaciones import servicios, ubicacion
from apps.publicaciones.models import Publicacion

from .conftest import crear_imagen, hacer_publicacion

pytestmark = pytest.mark.django_db

URL = "publicaciones:publicar_hallazgo"
EXACTO = Point(-68.3012, -54.8033, srid=4326)
ANIMAL = {"especie": "perro", "tamano": "mediano", "raza": "", "color": "marrón"}


def datos(**cambios):
    base = {
        "especie": "perro",
        "tamano": "mediano",
        "color": "marrón",
        "latitud": -54.8033,
        "longitud": -68.3012,
        "foto": crear_imagen(),
    }
    return {**base, **cambios}


# --- servicio ---


def test_publica_el_hallazgo_con_la_ubicacion_exacta(ana):
    publicacion = servicios.publicar_hallazgo(
        ana, animal=ANIMAL, archivo=crear_imagen(), punto=EXACTO
    )

    assert publicacion.tipo == Publicacion.Tipo.HALLAZGO
    assert publicacion.estado == Publicacion.Estado.VIGENTE
    assert publicacion.autor == ana
    assert publicacion.especie == "perro"
    assert publicacion.ubicacion.equals_exact(EXACTO, 1e-9)


def test_crea_una_ficha_sin_responsable_con_la_foto(ana):
    publicacion = servicios.publicar_hallazgo(
        ana, animal=ANIMAL, archivo=crear_imagen(), punto=EXACTO
    )

    ficha = publicacion.ficha
    assert ficha.estado == FichaAnimal.Estado.SIN_RESPONSABLE
    assert ficha.responsable is None
    assert Fotografia.objects.get().ficha == ficha


def test_con_el_animal_consigo_queda_a_cargo_de_quien_lo_publica(ana):
    publicacion = servicios.publicar_hallazgo(
        ana, animal=ANIMAL, archivo=crear_imagen(), punto=EXACTO, tiene_consigo=True
    )

    assert publicacion.ficha.cuidador == ana
    assert publicacion.ficha.sin_responsable_desde == timezone.localdate()


def test_sin_el_animal_consigo_no_queda_a_cargo_de_nadie(ana):
    publicacion = servicios.publicar_hallazgo(
        ana, animal=ANIMAL, archivo=crear_imagen(), punto=EXACTO
    )

    assert publicacion.ficha.cuidador is None
    assert publicacion.ficha.sin_responsable_desde is None


def test_no_toca_el_domicilio(ana, monkeypatch):
    def no_debe_llamarse(*args, **kwargs):
        raise AssertionError("el hallazgo no guarda ningún domicilio")

    monkeypatch.setattr(ubicacion, "registrar_domicilio", no_debe_llamarse)

    servicios.publicar_hallazgo(ana, animal=ANIMAL, archivo=crear_imagen(), punto=EXACTO)


def test_una_foto_invalida_no_deja_nada_a_medias(ana):
    with pytest.raises(ImagenInvalida):
        servicios.publicar_hallazgo(
            ana,
            animal=ANIMAL,
            archivo=SimpleUploadedFile("a.jpg", b"no es una imagen"),
            punto=EXACTO,
        )

    assert not FichaAnimal.objects.exists()
    assert not Publicacion.objects.exists()


# --- vista ---


def test_hay_que_iniciar_sesion(client):
    respuesta = client.get(reverse(URL))

    assert respuesta.status_code == 302
    assert respuesta.url.startswith(settings.LOGIN_URL)


def test_se_muestra_el_asistente(entrar, ana):
    respuesta = entrar(ana).get(reverse(URL))

    assert respuesta.status_code == 200
    assert "Publicar hallazgo" in respuesta.content.decode()


def test_publica_y_muestra_la_publicacion(entrar, ana):
    respuesta = entrar(ana).post(reverse(URL), datos())

    publicacion = Publicacion.objects.get()
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("publicaciones:detalle", args=[publicacion.pk])
    assert publicacion.tipo == Publicacion.Tipo.HALLAZGO
    assert publicacion.ficha.estado == FichaAnimal.Estado.SIN_RESPONSABLE


def test_marcar_que_lo_tiene_consigo_lo_deja_a_su_cargo(entrar, ana):
    entrar(ana).post(reverse(URL), datos(tiene_consigo="on"))

    assert Publicacion.objects.get().ficha.cuidador == ana


def test_sin_marcar_nada_no_queda_a_cargo_de_nadie(entrar, ana):
    entrar(ana).post(reverse(URL), datos())

    assert Publicacion.objects.get().ficha.cuidador is None


def test_texto_ofensivo_se_rechaza(entrar, ana):
    respuesta = entrar(ana).post(reverse(URL), datos(descripcion="mierda"))

    assert respuesta.status_code == 200
    assert "Texto ofensivo" in respuesta.content.decode()
    assert not Publicacion.objects.exists()
    assert not FichaAnimal.objects.exists()


def test_hacen_falta_foto_especie_y_ubicacion(entrar, ana):
    respuesta = entrar(ana).post(reverse(URL), {"color": "negro"})

    html = respuesta.content.decode()
    assert respuesta.status_code == 200
    assert "Subí una foto del animal" in html
    assert "Elegí la especie" in html
    assert "Indicá dónde lo encontraste" in html
    assert not Publicacion.objects.exists()


@override_config(MAX_PUBLICACIONES_HORA=1)
def test_el_limite_por_hora_responde_403(entrar, ana):
    hacer_publicacion(ana)

    respuesta = entrar(ana).post(reverse(URL), datos())

    assert respuesta.status_code == 403
    assert Publicacion.objects.count() == 1
