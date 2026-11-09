from django.http import JsonResponse
from django.views.decorators.http import require_GET

from . import capas


@require_GET
def datos(request):
    """Datos públicos del mapa (CU-19): solo lo vigente, con el punto que se puede mostrar."""
    return JsonResponse(capas.geojson(), content_type="application/geo+json")
