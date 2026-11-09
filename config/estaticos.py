from django.contrib.staticfiles.apps import StaticFilesConfig


class EstaticosConfig(StaticFilesConfig):
    """Archivos estáticos sin la fuente de Tailwind: solo se publica el CSS compilado."""

    ignore_patterns = [*StaticFilesConfig.ignore_patterns, "src/*"]
