import io

import numpy as np
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from model_bakery import baker
from PIL import Image, ImageDraw

from apps.fichas.forms import MAX_FOTOS
from apps.fichas.models import FichaAnimal
from apps.imagenes import vision
from apps.imagenes.models import Fotografia

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_temporal(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture(autouse=True)
def vision_falsa(monkeypatch):
    monkeypatch.setattr(vision, "analizar", lambda img: (np.ones(4, dtype=np.float32) / 2, True))


def imagen(nombre="foto.jpg", semilla=1):
    """Una imagen JPEG distinta por semilla (para no caer en el control de repetidas)."""
    img = Image.new("RGB", (64, 64), (semilla * 40 % 255, 90, 160))
    ImageDraw.Draw(img).rectangle((5 * semilla, 5, 40, 40), fill=(250, 200, semilla * 30 % 255))
    buffer = io.BytesIO()
    img.save(buffer, "JPEG")
    return SimpleUploadedFile(nombre, buffer.getvalue(), content_type="image/jpeg")


def test_se_puede_crear_una_ficha_con_fotos(entrar, ana):
    respuesta = entrar(ana).post(
        reverse("fichas:nueva"),
        {"especie": "perro", "nombre": "Rex", "fotos": [imagen(semilla=1), imagen(semilla=2)]},
    )

    ficha = FichaAnimal.objects.get(nombre="Rex")
    assert respuesta.status_code == 302
    assert ficha.fotografias.count() == 2


def test_se_puede_crear_una_ficha_sin_fotos(entrar, ana):
    respuesta = entrar(ana).post(reverse("fichas:nueva"), {"especie": "gato"})

    assert respuesta.status_code == 302
    assert FichaAnimal.objects.count() == 1
    assert not Fotografia.objects.exists()


def test_una_foto_invalida_no_crea_la_ficha(entrar, ana):
    falsa = SimpleUploadedFile("nota.jpg", b"no es una imagen", content_type="image/jpeg")

    respuesta = entrar(ana).post(reverse("fichas:nueva"), {"especie": "perro", "fotos": [falsa]})

    assert respuesta.status_code == 200
    assert "fotos" in respuesta.context["form"].errors
    assert not FichaAnimal.objects.exists()


def test_no_se_aceptan_mas_de_las_fotos_permitidas(entrar, ana):
    fotos = [imagen(semilla=n) for n in range(1, MAX_FOTOS + 2)]

    respuesta = entrar(ana).post(reverse("fichas:nueva"), {"especie": "perro", "fotos": fotos})

    assert respuesta.status_code == 200
    assert "fotos" in respuesta.context["form"].errors
    assert not FichaAnimal.objects.exists()


def test_se_puede_agregar_una_foto_al_editar(entrar, ana):
    ficha = baker.make(FichaAnimal, responsable=ana, especie="perro", nombre="Rex")

    respuesta = entrar(ana).post(
        reverse("fichas:editar", args=[ficha.pk]),
        {"especie": "perro", "nombre": "Rex", "fotos": [imagen()]},
    )

    assert respuesta.status_code == 302
    assert ficha.fotografias.count() == 1
