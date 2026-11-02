import logging
import uuid
from concurrent.futures import ThreadPoolExecutor

from constance import config
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from . import hashing, vision
from .models import Fotografia
from .procesamiento import ImagenInvalida, a_jpeg_bytes, abrir_y_limpiar  # noqa: F401

logger = logging.getLogger(__name__)

# Si la verificación tarda más, la foto se guarda igual y sin marca.
TIMEOUT_VERIFICACION = 10

_ejecutor = ThreadPoolExecutor(max_workers=2)


def _guardar_en_media(contenido: bytes) -> str:
    ahora = timezone.now()
    ruta = f"fotos/{ahora:%Y/%m}/{uuid.uuid4().hex}.jpg"
    return default_storage.save(ruta, ContentFile(contenido))


def _fotos_de_otros(autor, ficha):
    """Fotos con las que se compara: se ignoran las de la misma ficha y las del mismo autor."""
    otras = Fotografia.objects.all()
    if ficha is not None:
        otras = otras.exclude(ficha=ficha)
    if autor is not None:
        otras = otras.exclude(ficha__responsable=autor)
    return otras


def _es_repetida(otras, sha256, phash):
    if otras.filter(hash_sha256=sha256).exists():
        return True
    existentes = otras.exclude(hash_perceptual="").values_list("hash_perceptual", flat=True)
    return hashing.hay_repetida(phash, existentes, config.UMBRAL_PHASH)


def _verificar(img):
    """(embedding en bytes o None, hay animal o None). Si falla o tarda de más: (None, None)."""
    futuro = _ejecutor.submit(vision.analizar, img)
    try:
        vector, hay_animal = futuro.result(timeout=TIMEOUT_VERIFICACION)
    except Exception:  # modelo ausente, onnxruntime caído, tiempo agotado...
        logger.exception("La verificación falló; se guarda sin marca")
        return None, None
    return vision.a_bytes(vector), hay_animal


def registrar_fotografia(*, archivo, autor=None, ficha=None) -> Fotografia:
    """Valida, limpia, calcula hashes y guarda la foto.

    Lanza ImagenInvalida si el archivo no es una imagen: la vista decide qué mostrar.
    Una foto repetida o sin animal no se rechaza: se guarda con marca de revisión.
    Si la verificación falla, se guarda igual y sin marca.
    """
    img = abrir_y_limpiar(archivo)
    contenido = a_jpeg_bytes(img)
    sha256 = hashing.sha256_hex(contenido)
    phash = hashing.phash_hex(img)

    repetida = _es_repetida(_fotos_de_otros(autor, ficha), sha256, phash)
    embedding, hay_animal = _verificar(img)

    motivo = ""
    if repetida:
        motivo = Fotografia.MotivoRevision.DUPLICADA
    elif hay_animal is False:
        motivo = Fotografia.MotivoRevision.SIN_ANIMAL

    return Fotografia.objects.create(
        archivo=_guardar_en_media(contenido),
        hash_sha256=sha256,
        hash_perceptual=phash,
        embedding=embedding,
        tiene_animal=hay_animal,
        motivo_revision=motivo,
        ficha=ficha,
    )
