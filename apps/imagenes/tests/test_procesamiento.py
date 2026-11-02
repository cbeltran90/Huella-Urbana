import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.imagenes import procesamiento
from apps.imagenes.procesamiento import ImagenInvalida, a_jpeg_bytes, abrir_y_limpiar

from .conftest import crear_imagen


def test_el_exif_se_elimina():
    exif = Image.Exif()
    exif[0x010F] = "FabricanteDePrueba"
    original = crear_imagen(exif=exif)
    assert len(Image.open(io.BytesIO(original.read())).getexif()) == 1
    original.seek(0)

    resultado = a_jpeg_bytes(abrir_y_limpiar(original))

    assert len(Image.open(io.BytesIO(resultado)).getexif()) == 0


def test_la_rotacion_del_exif_se_aplica_antes_de_borrarlo():
    exif = Image.Exif()
    exif[0x0112] = 6  # girada 90°
    img = Image.new("RGB", (40, 20), "red")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", exif=exif)
    archivo = SimpleUploadedFile("a.jpg", buffer.getvalue())

    assert abrir_y_limpiar(archivo).size == (20, 40)


def test_las_imagenes_grandes_se_reducen():
    img = Image.new("RGB", (3000, 1500), "blue")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    archivo = SimpleUploadedFile("a.png", buffer.getvalue())

    assert max(abrir_y_limpiar(archivo).size) == procesamiento.MAX_LADO


def test_un_archivo_que_no_es_imagen_se_rechaza():
    with pytest.raises(ImagenInvalida):
        abrir_y_limpiar(SimpleUploadedFile("a.jpg", b"esto no es una imagen"))


def test_un_formato_no_permitido_se_rechaza():
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buffer, format="GIF")

    with pytest.raises(ImagenInvalida):
        abrir_y_limpiar(SimpleUploadedFile("a.gif", buffer.getvalue()))


def test_una_imagen_de_mas_de_10_mb_se_rechaza(monkeypatch):
    monkeypatch.setattr(procesamiento, "MAX_BYTES", 10)

    with pytest.raises(ImagenInvalida):
        abrir_y_limpiar(crear_imagen())
