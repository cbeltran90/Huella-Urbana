import numpy as np
import pytest
from django.conf import settings
from PIL import Image

from apps.imagenes import vision


def salida_con_mejores(*clases):
    salida = np.zeros(1000, dtype=np.float32)
    for peso, clase in enumerate(clases, start=1):
        salida[clase] = peso
    return salida


def test_un_perro_entre_las_mejores_clases_cuenta_como_animal():
    assert vision.hay_animal(salida_con_mejores(207)) is True  # golden retriever


def test_un_gato_entre_las_mejores_clases_cuenta_como_animal():
    assert vision.hay_animal(salida_con_mejores(281)) is True  # gato atigrado


def test_otra_cosa_no_cuenta_como_animal():
    assert vision.hay_animal(salida_con_mejores(417, 504)) is False  # globo, taza


def test_si_el_modelo_no_es_de_1000_clases_no_se_puede_decir():
    assert vision.hay_animal(np.zeros(512, dtype=np.float32)) is None


def test_bytes_ida_y_vuelta():
    vector = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)

    assert np.array_equal(vision.desde_bytes(vision.a_bytes(vector)), vector)


def test_coseno_de_vectores_iguales_y_opuestos():
    a = np.array([1, 0], dtype=np.float32)

    assert vision.similitud_coseno(a, a) == 1.0
    assert vision.similitud_coseno(a, -a) == -1.0


@pytest.mark.skipif(not settings.VISION_MODEL_PATH.exists(), reason="falta el modelo .onnx")
def test_con_el_modelo_real_el_embedding_tiene_norma_uno():
    vector = vision.embedding(Image.new("RGB", (300, 300), "orange"))

    assert round(float(np.linalg.norm(vector)), 3) == 1.0
