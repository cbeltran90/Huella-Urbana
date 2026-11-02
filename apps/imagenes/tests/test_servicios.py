import os
import time

import pytest
from django.core.files.storage import default_storage
from model_bakery import baker

from apps.fichas.models import FichaAnimal
from apps.imagenes import servicios
from apps.imagenes.models import Fotografia
from apps.imagenes.procesamiento import ImagenInvalida

from .conftest import crear_imagen

pytestmark = pytest.mark.django_db


def test_guarda_la_foto_con_sus_hashes(ana, vision_falsa):
    ficha = baker.make(FichaAnimal, responsable=ana)

    foto = servicios.registrar_fotografia(archivo=crear_imagen(), autor=ana, ficha=ficha)

    assert foto.ficha == ficha
    assert len(foto.hash_sha256) == 64
    assert len(foto.hash_perceptual) == 16
    assert foto.embedding is not None
    assert foto.tiene_animal is True
    assert foto.motivo_revision == ""
    assert default_storage.exists(foto.archivo)


def test_el_archivo_guardado_esta_re_codificado(ana, vision_falsa):
    foto = servicios.registrar_fotografia(archivo=crear_imagen(), autor=ana)

    from PIL import Image

    with default_storage.open(foto.archivo) as archivo:
        assert len(Image.open(archivo).getexif()) == 0


def test_una_foto_que_no_es_imagen_no_guarda_nada(ana, vision_falsa):
    from django.core.files.uploadedfile import SimpleUploadedFile

    with pytest.raises(ImagenInvalida):
        servicios.registrar_fotografia(archivo=SimpleUploadedFile("a.jpg", b"nada"), autor=ana)

    assert not Fotografia.objects.exists()


def test_sin_animal_se_marca_para_revision(ana, vision_falsa):
    import numpy as np

    vision_falsa["valor"] = (np.ones(4, dtype=np.float32) / 2, False)

    foto = servicios.registrar_fotografia(archivo=crear_imagen(), autor=ana)

    assert foto.tiene_animal is False
    assert foto.motivo_revision == Fotografia.MotivoRevision.SIN_ANIMAL


def test_una_foto_repetida_de_otro_autor_se_marca(ana, beto, vision_falsa):
    ficha_de_ana = baker.make(FichaAnimal, responsable=ana)
    servicios.registrar_fotografia(archivo=crear_imagen(), autor=ana, ficha=ficha_de_ana)
    ficha_de_beto = baker.make(FichaAnimal, responsable=beto)

    foto = servicios.registrar_fotografia(archivo=crear_imagen(), autor=beto, ficha=ficha_de_beto)

    assert foto.motivo_revision == Fotografia.MotivoRevision.DUPLICADA


def test_la_repetida_del_mismo_autor_no_se_marca(ana, vision_falsa):
    una = baker.make(FichaAnimal, responsable=ana)
    otra = baker.make(FichaAnimal, responsable=ana)
    servicios.registrar_fotografia(archivo=crear_imagen(), autor=ana, ficha=una)

    foto = servicios.registrar_fotografia(archivo=crear_imagen(), autor=ana, ficha=otra)

    assert foto.motivo_revision == ""


def test_la_repetida_de_la_misma_ficha_no_se_marca(ana, beto, vision_falsa):
    ficha = baker.make(FichaAnimal, responsable=ana)
    servicios.registrar_fotografia(archivo=crear_imagen(), autor=ana, ficha=ficha)

    foto = servicios.registrar_fotografia(archivo=crear_imagen(), autor=beto, ficha=ficha)

    assert foto.motivo_revision == ""


def test_si_el_modelo_falla_se_guarda_igual_y_sin_marca(ana, vision_falsa):
    vision_falsa["valor"] = FileNotFoundError("no hay modelo")

    foto = servicios.registrar_fotografia(archivo=crear_imagen(), autor=ana)

    assert foto.pk is not None
    assert foto.embedding is None
    assert foto.tiene_animal is None
    assert foto.motivo_revision == ""


def test_si_la_verificacion_tarda_de_mas_se_guarda_igual_y_sin_marca(
    ana, vision_falsa, monkeypatch
):
    def lenta(img):
        time.sleep(0.5)
        return vision_falsa["valor"]

    monkeypatch.setattr(servicios.vision, "analizar", lenta)
    monkeypatch.setattr(servicios, "TIMEOUT_VERIFICACION", 0.05)

    foto = servicios.registrar_fotografia(archivo=crear_imagen(), autor=ana)

    assert foto.pk is not None
    assert foto.tiene_animal is None
    assert foto.motivo_revision == ""


def test_al_borrar_la_ficha_se_borra_la_foto_y_su_archivo(ana, vision_falsa):
    ficha = baker.make(FichaAnimal, responsable=ana)
    foto = servicios.registrar_fotografia(archivo=crear_imagen(), autor=ana, ficha=ficha)
    ruta = default_storage.path(foto.archivo)
    assert os.path.exists(ruta)

    ficha.delete()

    assert not Fotografia.objects.filter(pk=foto.pk).exists()
    assert not os.path.exists(ruta)
