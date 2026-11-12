from urllib.parse import urlsplit

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from apps.cuentas.decoradores import cuenta_habilitada
from apps.cuentas.servicios import esta_suspendido
from apps.imagenes.servicios import ImagenInvalida

from . import permisos, servicios
from .forms import FichaConFotosForm
from .models import FichaAnimal


def _ficha_visible(request, pk):
    """La ficha, o 404 si no existe o el usuario no puede verla (no se revela que existe)."""
    ficha = get_object_or_404(FichaAnimal, pk=pk)
    if not permisos.puede_ver(request.user, ficha):
        raise Http404
    return ficha


def _principal(ficha):
    """La ficha en la que quedó fusionada (siguiendo la cadena), o la misma si no se fusionó."""
    for _ in range(5):  # tope por si algún dato quedara en ciclo
        if ficha.fusionada_en_id is None:
            break
        ficha = ficha.fusionada_en
    return ficha


@login_required
def mis_fichas(request):
    fichas = FichaAnimal.objects.filter(
        Q(responsable=request.user) | Q(cuidador=request.user), fusionada_en__isnull=True
    )
    contexto = {"fichas": fichas, "puede_crear": not esta_suspendido(request.user)}
    return render(request, "fichas/mis_fichas.html", contexto)


@cuenta_habilitada
def ficha_nueva(request):
    if request.method == "POST":
        form = FichaConFotosForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    ficha = servicios.crear_ficha(request.user, form.cleaned_data)
                    servicios.agregar_fotografias(ficha, request.user, form.cleaned_data["fotos"])
            except ImagenInvalida as error:
                form.add_error("fotos", str(error))
            else:
                return redirect("fichas:mis_fichas")
    else:
        form = FichaConFotosForm()
    return render(request, "fichas/ficha_form.html", {"form": form, "ficha": None})


def _volver(request, ficha):
    """A dónde lleva «Volver»: a la página de la que venía; si no se sabe, a "Mis fichas"."""
    anterior = request.META.get("HTTP_REFERER", "")
    propia = reverse("fichas:detalle", args=[ficha.pk])
    es_segura = url_has_allowed_host_and_scheme(
        anterior, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    )
    if anterior and es_segura and urlsplit(anterior).path != propia:
        return anterior
    return reverse("fichas:mis_fichas") if request.user.is_authenticated else ""


def ficha_detalle(request, pk):
    # Es una consulta pública: puede_ver oculta las fichas privadas a quien no corresponde.
    ficha = _ficha_visible(request, pk)
    principal = _principal(ficha)
    if principal != ficha:
        # La ficha se unió a otra: se muestra la del animal, con un aviso.
        return redirect(f"{reverse('fichas:detalle', args=[principal.pk])}?unida=1")
    suspendido = request.user.is_authenticated and esta_suspendido(request.user)
    puede_editar = permisos.puede_editar(request.user, ficha) and not suspendido
    fotos = ficha.fotografias.all()
    if not puede_editar:
        fotos = fotos.filter(motivo_revision="")  # las marcadas esperan la revisión
    contexto = {
        "ficha": ficha,
        "fotos": fotos,
        "unida": "unida" in request.GET,
        "volver": _volver(request, ficha),
        "puede_editar": puede_editar,
        "puede_baja": permisos.puede_dar_de_baja(request.user, ficha) and not suspendido,
    }
    return render(request, "fichas/ficha_detalle.html", contexto)


@cuenta_habilitada
def ficha_editar(request, pk):
    ficha = _ficha_visible(request, pk)
    if not permisos.puede_editar(request.user, ficha):
        raise PermissionDenied
    if request.method == "POST":
        form = FichaConFotosForm(request.POST, request.FILES, instance=ficha)
        if form.is_valid():
            try:
                with transaction.atomic():
                    servicios.editar_ficha(ficha, form.cleaned_data)
                    servicios.agregar_fotografias(ficha, request.user, form.cleaned_data["fotos"])
            except ImagenInvalida as error:
                form.add_error("fotos", str(error))
            else:
                return redirect("fichas:detalle", pk=ficha.pk)
    else:
        form = FichaConFotosForm(instance=ficha)
    return render(request, "fichas/ficha_form.html", {"form": form, "ficha": ficha})


@cuenta_habilitada
def ficha_baja(request, pk):
    ficha = _ficha_visible(request, pk)
    if not permisos.puede_dar_de_baja(request.user, ficha):
        raise PermissionDenied
    if request.method == "POST":
        servicios.dar_de_baja(ficha)
        return redirect("fichas:mis_fichas")
    return render(request, "fichas/ficha_confirmar_baja.html", {"ficha": ficha})
