"""Los estáticos se pueden publicar como en producción (ManifestStaticFilesStorage)."""

from django.core.management import call_command

MANIFIESTO = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"


def test_collectstatic_funciona_como_en_produccion(settings, tmp_path):
    settings.STATIC_ROOT = tmp_path
    settings.STORAGES = {**settings.STORAGES, "staticfiles": {"BACKEND": MANIFIESTO}}

    call_command("collectstatic", interactive=False, verbosity=0)

    assert (tmp_path / "staticfiles.json").exists()
    assert not (tmp_path / "src" / "input.css").exists()
