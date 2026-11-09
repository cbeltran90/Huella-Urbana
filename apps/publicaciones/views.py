from django.contrib.auth.decorators import login_required
from django.contrib.gis.geos import Point
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.limites import limite_publicaciones
from apps.cuentas.decoradores import cuenta_habilitada
from apps.cuentas.servicios import DomicilioInvalido
from apps.fichas.models import Coincidencia, FichaAnimal
from apps.fichas.permisos import es_moderador, puede_ver
from apps.imagenes.procesamiento import ImagenInvalida

from . import listados, resolucion, servicios, ubicacion, vinculacion
from .forms import AltaAdopcionForm, ExtravioForm, HallazgoForm
from .models import Publicacion


@cuenta_habilitada
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
            except DomicilioInvalido as error:
                form.add_error("latitud", str(error))
            else:
                return _destino(publicacion)
    else:
        form = ExtravioForm(**parametros)
    contexto = {
        "form": form,
        "tiene_domicilio": tiene_domicilio,
        "paso_inicial": form.paso_con_error() if form.is_bound else 1,
    }
    return render(request, "publicaciones/publicar_extravio.html", contexto)


def detalle(request, pk):
    # Consulta pública. Los avistamientos de fauna silvestre solo los ven su autor y los
    # moderadores (DER): para el resto no existen.
    publicacion = get_object_or_404(
        Publicacion.objects.exclude(estado=Publicacion.Estado.ELIMINADA).select_related("ficha"),
        pk=pk,
    )
    if publicacion.tipo == Publicacion.Tipo.AVISTAMIENTO and not (
        request.user.is_authenticated
        and (publicacion.autor_id == request.user.pk or es_moderador(request.user))
    ):
        raise Http404
    # La publicación muestra las fotos de su ficha (no tiene fotos propias).
    fotos = publicacion.ficha.fotografias.all() if publicacion.ficha else []
    contexto = {
        "publicacion": publicacion,
        "fotos": fotos,
        "puede_desvincular": vinculacion.puede_desvincular(publicacion, request.user),
    }
    return render(request, "publicaciones/detalle.html", contexto)


@cuenta_habilitada
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
                return _destino(publicacion)
    else:
        form = HallazgoForm()
    contexto = {"form": form, "paso_inicial": form.paso_con_error() if form.is_bound else 1}
    return render(request, "publicaciones/publicar_hallazgo.html", contexto)


@cuenta_habilitada
@limite_publicaciones
def alta_adopcion(request):
    tiene_domicilio = ubicacion.punto_de_domicilio(request.user) is not None
    if request.method == "POST":
        form = AltaAdopcionForm(request.POST, request.FILES, tiene_domicilio=tiene_domicilio)
        if form.is_valid():
            datos = form.cleaned_data
            punto = None
            if datos["latitud"] is not None and datos["longitud"] is not None:
                punto = Point(datos["longitud"], datos["latitud"], srid=4326)
            try:
                publicacion = servicios.alta_en_adopcion(
                    request.user,
                    animal=form.datos_ficha(),
                    archivos=datos["fotos"],
                    punto=punto,
                    descripcion=datos["descripcion"],
                    telefono_visible=datos["telefono_visible"],
                )
            except ImagenInvalida as error:
                form.add_error("fotos", str(error))
            except DomicilioInvalido as error:
                form.add_error("latitud", str(error))
            else:
                return _destino(publicacion)
    else:
        form = AltaAdopcionForm(tiene_domicilio=tiene_domicilio)
    contexto = {
        "form": form,
        "tiene_domicilio": tiene_domicilio,
        "paso_inicial": form.paso_con_error() if form.is_bound else 1,
    }
    return render(request, "publicaciones/alta_adopcion.html", contexto)


def _destino(publicacion):
    """Tras publicar: si hay candidatas, primero se muestran; si no, va al detalle."""
    if vinculacion.proponer_coincidencias(publicacion):
        return redirect("publicaciones:candidatas", pk=publicacion.pk)
    return redirect("publicaciones:detalle", pk=publicacion.pk)


@login_required
@cuenta_habilitada
def candidatas(request, pk):
    publicacion = get_object_or_404(Publicacion, pk=pk, autor=request.user)
    coincidencias = publicacion.coincidencias.select_related("ficha")
    if request.method == "POST":
        ficha_id = request.POST.get("ficha")
        if ficha_id:  # Eligió una candidata
            coincidencia = get_object_or_404(coincidencias, ficha_id=ficha_id)
            vinculacion.vincular(publicacion, coincidencia.ficha, request.user)
        return redirect("publicaciones:detalle", pk=publicacion.pk)  # "Ninguna corresponde"
    return render(
        request,
        "publicaciones/candidatas.html",
        {"publicacion": publicacion, "coincidencias": coincidencias},
    )


@login_required
@cuenta_habilitada
@require_POST
def responder_coincidencia(request, pk):
    coincidencia = get_object_or_404(Coincidencia, pk=pk)
    confirmar = request.POST.get("accion") == "confirmar"
    try:
        vinculacion.responder(coincidencia, request.user, confirmar=confirmar)
    except PermissionError:
        raise PermissionDenied from None
    return redirect("publicaciones:coincidencias")


@login_required
@cuenta_habilitada
def desvincular(request, pk):
    publicacion = get_object_or_404(
        Publicacion.objects.exclude(estado=Publicacion.Estado.ELIMINADA).select_related("ficha"),
        pk=pk,
    )
    if not vinculacion.puede_desvincular(publicacion, request.user):
        raise PermissionDenied
    if request.method == "POST":  # sin POST (o si cancela) no se cambia nada
        vinculacion.desvincular(publicacion, request.user)
        return redirect("publicaciones:detalle", pk=publicacion.pk)
    return render(request, "publicaciones/desvincular_confirmar.html", {"publicacion": publicacion})


def _volver_desde(usuario, ficha):
    """La ficha, si quien resuelve la puede ver; si no (ficha privada), el listado."""
    if puede_ver(usuario, ficha):
        return reverse("fichas:detalle", args=[ficha.pk])
    return reverse("publicaciones:perdidos")


@login_required
@cuenta_habilitada
def resolver_caso(request, pk):
    """Cierra el caso de extravío de la ficha (CU-14), después de pedir confirmación."""
    ficha = get_object_or_404(FichaAnimal, pk=pk)
    if not resolucion.puede_resolver(request.user, ficha):
        raise PermissionDenied
    volver = _volver_desde(request.user, ficha)
    if request.method == "POST":  # sin POST (o si cancela) no se cambia nada
        resolucion.resolver_caso(ficha, request.user)
        return redirect(volver)
    return render(request, "publicaciones/resolver_caso_confirmar.html", {"volver": volver})


@login_required
@cuenta_habilitada
def coincidencias(request):
    """Coincidencias que esperan la decisión de esta persona (confirmar o descartar)."""
    contexto = {"coincidencias": vinculacion.pendientes_para(request.user)}
    return render(request, "publicaciones/coincidencias.html", contexto)


POR_PAGINA = 12


def _listado(request, plantilla, publicaciones, contexto):
    """Muestra una página del listado; si la pide htmx ("Ver más"), solo sus tarjetas."""
    consulta = request.GET.copy()
    consulta.pop("pagina", None)
    contexto |= {
        "pagina": Paginator(publicaciones, POR_PAGINA).get_page(request.GET.get("pagina")),
        "consulta": consulta.urlencode(),
        "filtros": request.GET,
        "especies": FichaAnimal.Especie.choices,
        "tamanos": FichaAnimal.Tamano.choices,
    }
    if request.headers.get("HX-Request"):
        plantilla = "publicaciones/_pagina_listado.html"
    return render(request, plantilla, contexto)


def perdidos(request):
    """Listado público de perdidos (CU-20): visitantes incluidos, sin cambios en el sistema."""
    filtros = request.GET
    punto = listados.punto_desde(filtros.get("lat"), filtros.get("lon"))
    publicaciones = listados.perdidos(
        tipo=filtros.get("tipo", ""),
        especie=filtros.get("especie", ""),
        tamano=filtros.get("tamano", ""),
        punto=punto,
    )
    contexto = {
        "con_punto": punto is not None,
        "tipos": [(t.value, t.label) for t in listados.TIPOS_PERDIDOS],
    }
    return _listado(request, "publicaciones/perdidos.html", publicaciones, contexto)


def disponibles(request):
    """Listado público de disponibles (CU-20): adopción y tránsito, sin orden por cercanía."""
    filtros = request.GET
    publicaciones = listados.disponibles(
        tipo=filtros.get("tipo", ""),
        especie=filtros.get("especie", ""),
        tamano=filtros.get("tamano", ""),
    )
    contexto = {"tipos": [(t.value, t.label) for t in listados.TIPOS_DISPONIBLES]}
    return _listado(request, "publicaciones/disponibles.html", publicaciones, contexto)
