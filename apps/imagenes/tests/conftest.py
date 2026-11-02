import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageDraw

from apps.cuentas.models import EstadoCuenta
from apps.imagenes import vision


def _crear_usuario(django_user_model, nombre):
    return django_user_model.objects.create_user(
        f"{nombre.lower()}@ejemplo.com",
        nombre,
        "clave-de-prueba-1",
        estado_cuenta=EstadoCuenta.ACTIVA,
    )


@pytest.fixture
def ana(django_user_model):
    return _crear_usuario(django_user_model, "Ana")


@pytest.fixture
def beto(django_user_model):
    return _crear_usuario(django_user_model, "Beto")


@pytest.fixture(autouse=True)
def media_temporal(settings, tmp_path):
    """Los archivos de los tests van a una carpeta temporal, no a media/."""
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def vision_falsa(monkeypatch):
    """Reemplaza el modelo ONNX: devuelve un vector fijo y «hay animal»."""
    import numpy as np

    resultado = {"valor": (np.ones(4, dtype=np.float32) / 2, True)}

    def analizar(img):
        valor = resultado["valor"]
        if isinstance(valor, Exception):
            raise valor
        return valor

    monkeypatch.setattr(vision, "analizar", analizar)
    return resultado


def crear_imagen(*, lado=200, exif=None, formato="JPEG"):
    """Imagen de prueba con un dibujo (mitad blanca, mitad negra) como archivo subido."""
    img = Image.new("RGB", (lado, lado), "black")
    ImageDraw.Draw(img).rectangle([0, 0, lado // 2, lado], fill="white")
    buffer = io.BytesIO()
    opciones = {"exif": exif} if exif is not None else {}
    img.save(buffer, format=formato, **opciones)
    return SimpleUploadedFile("foto.jpg", buffer.getvalue(), content_type="image/jpeg")


@pytest.fixture
def imagen():
    return crear_imagen
