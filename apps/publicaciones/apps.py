from django.apps import AppConfig


class PublicacionesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.publicaciones"

    def ready(self):
        from . import eliminacion  # noqa: F401  (registra su paso al eliminar una cuenta)
