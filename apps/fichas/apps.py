from django.apps import AppConfig


class FichasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.fichas"

    def ready(self):
        from . import eliminacion  # noqa: F401  (registra su paso al eliminar una cuenta)
