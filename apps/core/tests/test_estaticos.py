"""Los estáticos se pueden publicar como en producción (ManifestStaticFilesStorage)."""

import pytest
from django.contrib.staticfiles import finders
from django.core.management import call_command

MANIFIESTO = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
FUENTES = [
    "atkinson-hyperlegible-latin-400-normal.woff2",
    "atkinson-hyperlegible-latin-700-normal.woff2",
    "atkinson-hyperlegible-latin-400-italic.woff2",
]


def test_collectstatic_funciona_como_en_produccion(settings, tmp_path):
    settings.STATIC_ROOT = tmp_path
    settings.STORAGES = {**settings.STORAGES, "staticfiles": {"BACKEND": MANIFIESTO}}

    call_command("collectstatic", interactive=False, verbosity=0)

    assert (tmp_path / "staticfiles.json").exists()
    assert not (tmp_path / "src" / "input.css").exists()


@pytest.mark.parametrize("archivo", FUENTES)
def test_la_fuente_se_sirve_desde_el_sitio(archivo):
    assert finders.find(f"vendor/fuentes/{archivo}")
