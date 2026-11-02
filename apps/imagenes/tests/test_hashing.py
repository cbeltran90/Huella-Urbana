from PIL import Image, ImageDraw

from apps.imagenes import hashing


def dibujo(lado):
    img = Image.new("RGB", (lado, lado), "black")
    ImageDraw.Draw(img).rectangle([0, 0, lado // 2, lado], fill="white")
    return img


def test_sha256_tiene_64_caracteres_y_es_estable():
    assert len(hashing.sha256_hex(b"hola")) == 64
    assert hashing.sha256_hex(b"hola") == hashing.sha256_hex(b"hola")
    assert hashing.sha256_hex(b"hola") != hashing.sha256_hex(b"chau")


def test_el_hash_perceptual_tiene_16_caracteres():
    assert len(hashing.phash_hex(dibujo(200))) == 16


def test_la_misma_foto_en_otro_tamano_es_casi_igual():
    grande = hashing.phash_hex(dibujo(400))
    chica = hashing.phash_hex(dibujo(100))

    assert hashing.distancia(grande, chica) <= 5


def test_hay_repetida_respeta_el_umbral():
    base = "ffffffffffffffff"
    cercano = "fffffffffffffffe"  # 1 bit de diferencia
    lejano = "0000000000000000"  # 64 bits de diferencia

    assert hashing.hay_repetida(base, [cercano], umbral=5)
    assert not hashing.hay_repetida(base, [lejano], umbral=5)
    assert not hashing.hay_repetida(base, [], umbral=5)
    assert not hashing.hay_repetida(base, [""], umbral=5)
