from django.conf import settings


def mapa(request):
    return {
        "mapa_config": {
            "tiles_url": settings.MAPA_TILES_URL,
            "atribucion": settings.MAPA_TILES_ATRIBUCION,
        }
    }
