from django.apps import AppConfig


class NotificacionesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notificaciones"

    def ready(self):
        from . import eliminacion  # noqa: F401 (registra su paso al eliminar una cuenta)
