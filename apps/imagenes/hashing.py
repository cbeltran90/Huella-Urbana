import hashlib

import imagehash


def sha256_hex(contenido: bytes) -> str:
    """Huella exacta del archivo ya re-codificado (64 caracteres hexadecimales)."""
    return hashlib.sha256(contenido).hexdigest()


def phash_hex(img) -> str:
    """Hash perceptual: una misma foto con otro tamaño o compresión da casi el mismo valor."""
    return str(imagehash.phash(img))  # 16 caracteres hexadecimales


def distancia(hash_a: str, hash_b: str) -> int:
    """Distancia de Hamming entre dos hashes perceptuales."""
    return imagehash.hex_to_hash(hash_a) - imagehash.hex_to_hash(hash_b)


def hay_repetida(phash: str, existentes, umbral: int) -> bool:
    return any(h and distancia(phash, h) <= umbral for h in existentes)
