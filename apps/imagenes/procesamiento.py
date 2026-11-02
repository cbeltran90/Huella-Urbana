import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_LADO = 1600
MAX_BYTES = 10 * 1024 * 1024
FORMATOS_PERMITIDOS = {"JPEG", "PNG", "WEBP"}


class ImagenInvalida(Exception):
    """La imagen subida no se puede procesar."""


def abrir_y_limpiar(archivo) -> Image.Image:
    """Devuelve una imagen RGB sin metadatos, rotada según su EXIF y reducida."""
    if archivo.size > MAX_BYTES:
        raise ImagenInvalida("La imagen supera los 10 MB.")

    try:
        Image.open(archivo).verify()  # detecta archivos corruptos
        archivo.seek(0)
        img = Image.open(archivo)
        if img.format not in FORMATOS_PERMITIDOS:
            raise ImagenInvalida("Formato no permitido (usá JPEG, PNG o WEBP).")
        # La orientación se aplica ANTES de perder el EXIF; si no, la foto queda de costado.
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
    except ImagenInvalida:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ImagenInvalida("El archivo no es una imagen válida.") from exc

    img.thumbnail((MAX_LADO, MAX_LADO))
    img.info.clear()  # sin EXIF, sin GPS, sin perfiles embebidos
    return img


def a_jpeg_bytes(img: Image.Image) -> bytes:
    """Re-codifica a JPEG. No se pasa `exif=`, así que no se escribe ningún metadato."""
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85, optimize=True)
    return buffer.getvalue()
