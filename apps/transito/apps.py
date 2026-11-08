from django.apps import AppConfig


class TransitoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.transito"

    def ready(self):
        from . import eliminacion  # noqa: F401 (registra su paso al eliminar una cuenta)
