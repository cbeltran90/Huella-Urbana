"""Genera el ícono de Huella Urbana: una huella de perro dibujada con crestas
de huella dactilar, sin borde y con fondo transparente.

Cada almohadilla se dibuja con crestas que siguen su forma, alrededor de un
núcleo corrido (como en una huella dactilar real), y cada cresta tiene un corte.
En la almohadilla grande las crestas externas quedan abiertas hacia abajo
(patrón de «lazo»). No hay contorno: la silueta la dan las propias crestas.

Uso, desde la raíz del repo:
    python3 scripts/generar_icono.py
Escribe static/img/icono.svg (detallado, para 180 px o más) y static/img/favicon.svg
(menos crestas y más gruesas, para la pestaña; en modo oscuro usa el verde de la skin
oscura). Los PNG y el .ico se derivan de esos dos archivos:
    rsvg-convert -w 180 -h 180 static/img/icono.svg -o static/img/apple-touch-icon.png
    rsvg-convert -w 192 -h 192 static/img/icono.svg -o static/img/icon-192.png
    rsvg-convert -w 512 -h 512 static/img/icono.svg -o static/img/icon-512.png
    (favicon.ico: 16, 32 y 48 px renderizados desde favicon.svg, juntos con Pillow)
"""

import math
import sys
from pathlib import Path

COLOR = "#2e6b4e"  # --hu-primario de la skin oficial: el color del título

# Dedos: centro, semiejes y giro (grados). Caja de 100 x 100.
DEDOS = [
    (18.5, 45.0, 9.5, 12.5, -32),
    (36.5, 22.0, 10.0, 13.5, -10),
    (63.5, 22.0, 10.0, 13.5, 10),
    (81.5, 45.0, 9.5, 12.5, 32),
]
# Almohadilla principal: triángulo redondeado con el vértice hacia los dedos.
ALMOHADILLA = (50.0, 67.0, 25.0, 18.0)  # cx, cy, semiancho, semialto


def contorno_dedo(t, rx, ry):
    return rx * math.cos(t), ry * math.sin(t)


def contorno_almohadilla(t, a, b):
    # y crece hacia abajo; sin(t) = -1 es el vértice superior.
    x, y = a * math.cos(t), b * math.sin(t)
    x *= 1 - 0.36 * (1 - math.sin(t)) / 2  # más angosta arriba
    y += 2.2 * math.exp(-(math.cos(t) ** 2) / 0.04) * max(math.sin(t), 0)  # leve hendidura abajo
    y -= 2.2 * max(math.sin(t), 0) ** 6  # base casi plana
    return x, y


def cresta(forma, cx, cy, rot, escala, nucleo, desde, hasta, onda, fase, n):
    """Una cresta: la forma escalada alrededor del núcleo, entre dos ángulos."""
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    nx, ny = nucleo
    puntos = []
    for i in range(n + 1):
        t = desde + (hasta - desde) * i / n
        x, y = forma(t)
        k = escala * (1 + onda * math.sin(4 * t + fase))
        # Escala alrededor del núcleo (no del centro): crestas más juntas de un lado.
        px, py = nx + (x - nx) * k, ny + (y - ny) * k
        puntos.append((cx + px * c - py * s, cy + px * s + py * c))
    # Tras la M, los pares siguientes son líneas implícitas: archivo más liviano.
    return "M" + " ".join(f"{x:.1f} {y:.1f}" for x, y in puntos)


def crestas(forma, cx, cy, rot, radio, nucleo, paso, grosor, onda, puntos, abiertas_abajo=0):
    caminos = []
    exterior = radio - grosor * 0.6  # la cresta externa queda dentro de la silueta
    k = 0
    while True:
        r = exterior - k * paso
        escala = r / radio
        if escala < 0.08:
            break
        fase = k * 1.7
        if k < abiertas_abajo:
            # Lazo: abierta hacia abajo, con las puntas bajando a los costados.
            hueco = 1.05 - 0.25 * k
            desde, hasta = math.pi / 2 + hueco / 2, math.pi / 2 + 2 * math.pi - hueco / 2
        else:
            # Corte chico en un lugar distinto de cada cresta.
            hueco = 0.55 if escala > 0.3 else 0.0
            centro = 0.9 + k * 2.3
            desde, hasta = centro + hueco / 2, centro + 2 * math.pi - hueco / 2
        caminos.append(cresta(forma, cx, cy, rot, escala, nucleo, desde, hasta, onda, fase, puntos))
        k += 1
    return caminos


def svg(paso, grosor, onda, puntos, verde_oscuro=None):
    partes = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">',
        "  <title>Huella Urbana</title>",
    ]
    if verde_oscuro:
        regla = f"@media (prefers-color-scheme: dark) {{ g {{ stroke: {verde_oscuro}; }} }}"
        partes.append(f"  <style>{regla}</style>")
    partes += [
        f'  <g fill="none" stroke="{COLOR}" stroke-width="{grosor}" '
        'stroke-linecap="round" stroke-linejoin="round">',
    ]
    for cx, cy, rx, ry, rot in DEDOS:

        def forma(t, rx=rx, ry=ry):
            return contorno_dedo(t, rx, ry)

        nucleo = (0.0, ry * 0.22)  # hacia la base del dedo
        for d in crestas(forma, cx, cy, rot, min(rx, ry), nucleo, paso, grosor, onda, puntos):
            partes.append(f'    <path d="{d}"/>')
    cx, cy, a, b = ALMOHADILLA

    def forma_alm(t):
        return contorno_almohadilla(t, a, b)

    nucleo = (0.0, b * 0.18)
    for d in crestas(forma_alm, cx, cy, 0, b, nucleo, paso, grosor, onda, puntos, abiertas_abajo=2):
        partes.append(f'    <path d="{d}"/>')
    partes += ["  </g>", "</svg>"]
    return "\n".join(partes) + "\n"


if __name__ == "__main__":
    salida = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("static/img")
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "icono.svg").write_text(svg(paso=3.6, grosor=1.9, onda=0.02, puntos=56))
    (salida / "favicon.svg").write_text(
        svg(paso=6.4, grosor=3.6, onda=0.0, puntos=36, verde_oscuro="#6fc198")
    )
    print(f"Íconos escritos en {salida}")
