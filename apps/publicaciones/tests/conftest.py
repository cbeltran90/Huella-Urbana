import io

import pytest
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker
from PIL import Image, ImageDraw

from apps.cuentas.models import EstadoCuenta
from apps.imagenes import vision
from apps.publicaciones import ubicacion
from apps.publicaciones.models import Publicacion

BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"
DOMICILIO = Point(-68.3040, -54.8025, srid=4326)  # el punto ya desplazado


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
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture(autouse=True)
def vision_falsa(monkeypatch):
    """Sin modelo ONNX: devuelve un vector fijo y "hay animal"."""
    import numpy as np

    monkeypatch.setattr(vision, "analizar", lambda img: (np.ones(4, dtype=np.float32) / 2, True))


@pytest.fixture
def con_domicilio(monkeypatch):
    monkeypatch.setattr(ubicacion, "punto_de_domicilio", lambda usuario: DOMICILIO)
    return DOMICILIO


@pytest.fixture
def entrar(client):
    def _entrar(usuario):
        client.force_login(usuario, backend=BACKEND_MODELO)
        return client

    return _entrar


def crear_imagen():
    img = Image.new("RGB", (200, 200), "black")
    ImageDraw.Draw(img).rectangle([0, 0, 100, 200], fill="white")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return SimpleUploadedFile("foto.jpg", buffer.getvalue(), content_type="image/jpeg")


def hacer_publicacion(autor, **campos):
    datos = {"tipo": Publicacion.Tipo.EXTRAVIO, "ubicacion": DOMICILIO, **campos}
    return baker.make(Publicacion, autor=autor, **datos)
