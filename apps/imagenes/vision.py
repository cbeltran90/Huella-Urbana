import logging
import threading

import numpy as np
from django.conf import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_sesion = None

_MEDIA = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_DESVIO = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# Clases de ImageNet que son perros (151-268) y gatos domésticos (281-285).
# Solo vale para modelos con las 1000 clases de ImageNet, como MobileNetV2.
_CLASES_ANIMAL = set(range(151, 269)) | set(range(281, 286))
_CLASES_IMAGENET = 1000
_TOP = 5


def _obtener_sesion():
    global _sesion
    if _sesion is None:
        with _lock:
            if _sesion is None:
                import onnxruntime as ort

                ruta = settings.VISION_MODEL_PATH
                if not ruta.exists():
                    raise FileNotFoundError(f"No existe el modelo: {ruta}")
                opciones = ort.SessionOptions()
                opciones.intra_op_num_threads = 2
                _sesion = ort.InferenceSession(
                    str(ruta), sess_options=opciones, providers=["CPUExecutionProvider"]
                )
                logger.info("Sesión ONNX cargada: %s", ruta.name)
    return _sesion


def _normalizar(vector: np.ndarray) -> np.ndarray:
    norma = np.linalg.norm(vector)
    return vector / norma if norma else vector


def hay_animal(salida: np.ndarray):
    """True o False según las mejores clases; None si el modelo no es de 1000 clases."""
    if salida.size != _CLASES_IMAGENET:
        return None
    mejores = np.argsort(salida)[-_TOP:]
    return any(int(clase) in _CLASES_ANIMAL for clase in mejores)


def analizar(img):
    """Una sola pasada por el modelo: (embedding normalizado, hay animal o None)."""
    sesion = _obtener_sesion()
    reducida = img.resize((224, 224))
    datos = (np.asarray(reducida, dtype=np.float32) / 255.0 - _MEDIA) / _DESVIO
    entrada = datos.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)
    salida = sesion.run(None, {sesion.get_inputs()[0].name: entrada})[0]
    vector = salida.reshape(-1).astype(np.float32)
    return _normalizar(vector), hay_animal(vector)


def embedding(img) -> np.ndarray:
    """Vector normalizado (norma 1) de la imagen."""
    return analizar(img)[0]


def similitud_coseno(a: np.ndarray, b: np.ndarray) -> float:
    """Con vectores normalizados, el coseno es el producto punto."""
    return float(np.dot(a, b))


def a_bytes(vector: np.ndarray) -> bytes:
    return vector.astype(np.float32).tobytes()


def desde_bytes(datos: bytes) -> np.ndarray:
    return np.frombuffer(datos, dtype=np.float32)
