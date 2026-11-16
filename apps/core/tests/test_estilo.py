"""Las plantillas usan los tokens del sitio (bg-primario, text-suave…), no los de Tailwind."""

import re
from pathlib import Path

import pytest

PLANTILLAS = Path(__file__).resolve().parents[3] / "templates"

COLOR_TAILWIND = re.compile(
    r"\b(?:bg|text|border|divide|ring|outline|decoration|accent|fill|stroke|from|via|to|placeholder|shadow)"
    r"-(?:white|black|(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan"
    r"|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3})\b"
)

# Plantillas del admin: usan los colores de Unfold, no los del sitio.
NO_SE_REVISAN = {"transito/admin_retirar_rol.html"}

# Los marcadores del mapa llevan el color de su capa (apps/mapa/capas.py) con la letra en blanco.
PERMITIDOS = {"mapa/mapa.html": {"text-white", "border-white"}}


def plantillas():
    rutas = sorted(PLANTILLAS.rglob("*.html"))
    nombres = [ruta.relative_to(PLANTILLAS).as_posix() for ruta in rutas]
    return [nombre for nombre in nombres if nombre not in NO_SE_REVISAN]


@pytest.mark.parametrize("nombre", plantillas())
def test_la_plantilla_no_usa_colores_de_tailwind(nombre):
    texto = (PLANTILLAS / nombre).read_text(encoding="utf-8")
    colores = set(COLOR_TAILWIND.findall(texto)) - PERMITIDOS.get(nombre, set())

    assert not colores, f"{nombre} usa {sorted(colores)}: usá los tokens de static/src/input.css"


@pytest.mark.parametrize(
    "clase", ["bg-emerald-600", "hover:text-stone-900", "border-white", "bg-red-50/50"]
)
def test_detecta_los_colores_de_tailwind(clase):
    assert COLOR_TAILWIND.search(clase)


@pytest.mark.parametrize("clase", ["bg-primario", "text-suave", "border-acento", "boton-peligro"])
def test_no_confunde_los_tokens_del_sitio(clase):
    assert not COLOR_TAILWIND.search(clase)
