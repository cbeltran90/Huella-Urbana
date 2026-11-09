from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.cuentas import geo
from apps.publicaciones.models import Publicacion

from . import capas


@require_GET
def mapa(request):
    """Mapa público (CU-19): visitantes incluidos, sin cambios en el sistema."""
    contexto = {
        "leyendas": capas.LEYENDAS,
        "capas_config": {
            "datos_url": reverse("mapa:datos"),
            "resumen_url": reverse("mapa:resumen", args=[0]),
            "leyendas": capas.LEYENDAS,
            "tipos": dict(Publicacion.Tipo.choices),
            # El mapa no se puede mover fuera del ejido urbano (RNF6).
            "limites": [
                [geo.LATITUD_MIN, geo.LONGITUD_MIN],
                [geo.LATITUD_MAX, geo.LONGITUD_MAX],
            ],
        },
    }
    return render(request, "mapa/mapa.html", contexto)


@require_GET
def datos(request):
    """Datos públicos del mapa (CU-19): solo lo vigente, con el punto que se puede mostrar."""
    return JsonResponse(capas.geojson(), content_type="application/geo+json")


@require_GET
def resumen(request, pk):
    """Resumen de una publicación del mapa, al tocar su marcador (CU-19)."""
    publicacion = get_object_or_404(capas.vigentes().select_related("ficha"), pk=pk)
    if not request.headers.get("HX-Request"):
        # Abierto directamente, sin el mapa: va al detalle completo.
        return redirect("publicaciones:detalle", pk=pk)
    ficha = publicacion.ficha
    contexto = {
        "publicacion": publicacion,
        "ficha_publica": ficha is not None and not ficha.es_privada,
        "foto": ficha.fotografias.first() if ficha else None,
    }
    return render(request, "mapa/_resumen.html", contexto)
