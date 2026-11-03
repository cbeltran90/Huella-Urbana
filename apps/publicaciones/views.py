from django.contrib.auth.decorators import login_required
from django.contrib.gis.geos import Point
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.limites import limite_publicaciones
from apps.imagenes.procesamiento import ImagenInvalida

from . import servicios, ubicacion
from .forms import ExtravioForm, HallazgoForm
from .models import Publicacion


@login_required
@limite_publicaciones
def publicar_extravio(request):
    tiene_domicilio = ubicacion.punto_de_domicilio(request.user) is not None
    parametros = {"usuario": request.user, "tiene_domicilio": tiene_domicilio}
    if request.method == "POST":
        form = ExtravioForm(request.POST, request.FILES, **parametros)
        if form.is_valid():
            datos = form.cleaned_data
            punto = None
            if datos["latitud"] is not None and datos["longitud"] is not None:
                punto = Point(datos["longitud"], datos["latitud"], srid=4326)
            try:
                publicacion = servicios.publicar_extravio(
                    request.user,
                    ficha=datos["ficha"],
                    animal=form.datos_animal(),
                    estado_aparente=datos["estado_aparente"],
                    descripcion=datos["descripcion"],
                    archivo=datos["foto"],
                    punto=punto,
                )
            except ImagenInvalida as error:
                form.add_error("foto", str(error))
            else:
                return redirect("publicaciones:detalle", pk=publicacion.pk)
    else:
        form = ExtravioForm(**parametros)
    contexto = {
        "form": form,
        "tiene_domicilio": tiene_domicilio,
        "paso_inicial": form.paso_con_error() if form.is_bound else 1,
    }
    return render(request, "publicaciones/publicar_extravio.html", contexto)


@login_required
def detalle(request, pk):
    publicacion = get_object_or_404(
        Publicacion.objects.exclude(estado=Publicacion.Estado.ELIMINADA).select_related("ficha"),
        pk=pk,
    )
    # La publicación muestra las fotos de su ficha (no tiene fotos propias).
    fotos = publicacion.ficha.fotografias.all() if publicacion.ficha else []
    return render(
        request, "publicaciones/detalle.html", {"publicacion": publicacion, "fotos": fotos}
    )


@login_required
@limite_publicaciones
def publicar_hallazgo(request):
    if request.method == "POST":
        form = HallazgoForm(request.POST, request.FILES)
        if form.is_valid():
            datos = form.cleaned_data
            punto = Point(datos["longitud"], datos["latitud"], srid=4326)
            try:
                publicacion = servicios.publicar_hallazgo(
                    request.user,
                    animal=form.datos_animal(),
                    archivo=datos["foto"],
                    punto=punto,
                    estado_aparente=datos["estado_aparente"],
                    descripcion=datos["descripcion"],
                    tiene_consigo=datos["tiene_consigo"],
                )
            except ImagenInvalida as error:
                form.add_error("foto", str(error))
            else:
                return redirect("publicaciones:detalle", pk=publicacion.pk)
    else:
        form = HallazgoForm()
    contexto = {"form": form, "paso_inicial": form.paso_con_error() if form.is_bound else 1}
    return render(request, "publicaciones/publicar_hallazgo.html", contexto)
