from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.cuentas.decoradores import cuenta_habilitada
from apps.fichas import permisos
from apps.fichas.models import FichaAnimal
from apps.publicaciones.models import Publicacion
from apps.transito.forms import PostulacionForm
from apps.transito.models import Postulacion

from . import eleccion, postulaciones
from .forms import ElegirForm


@cuenta_habilitada
def postular(request, ficha_pk):
    """Postularse para adoptar un animal disponible (CU-28)."""
    ficha = get_object_or_404(FichaAnimal, pk=ficha_pk)
    if not permisos.puede_ver(request.user, ficha):
        raise Http404
    motivo = postulaciones.motivo_para_no_postularse(request.user, ficha)
    form = PostulacionForm(request.POST or None)
    if motivo is None and form.is_valid():
        try:
            postulaciones.postular_adopcion(request.user, ficha, form.cleaned_data["contacto"])
        except postulaciones.PostulacionNoPermitida as error:
            motivo = (error.codigo, error.mensaje)
        except postulaciones.ContactoInvalido as error:
            form.add_error("contacto", str(error))
        else:
            destino = reverse("fichas:detalle", args=[ficha.pk])
            return redirect(f"{destino}?postulado_adopcion=1")
    contexto = {
        "ficha": ficha,
        "form": form,
        "motivo": motivo,
        "advertencias": postulaciones.advertencias_de_postulacion(request.user, ficha),
    }
    return render(request, "adopcion/postular.html", contexto)


@cuenta_habilitada
def postulantes(request, ficha_pk):
    """Quienes se postularon para adoptar, para que quien elige decida (CU-29)."""
    ficha = get_object_or_404(FichaAnimal, pk=ficha_pk)
    if not permisos.puede_ver(request.user, ficha):
        raise Http404
    if not eleccion.puede_elegir(request.user, ficha):
        raise PermissionDenied
    pendientes = eleccion.postulantes_de(ficha).select_related(
        "usuario__domicilio", "usuario__perfil_adoptante"
    )
    contexto = {
        "ficha": ficha,
        "elegida": eleccion.elegida_de(ficha),
        "postulantes": [
            (postulacion, eleccion.dudas_de(postulacion)) for postulacion in pendientes
        ],
    }
    return render(request, "adopcion/postulantes.html", contexto)


def _telefono_publicado(ficha):
    """El teléfono de la publicación de adopción vigente, para no tener que escribirlo de nuevo."""
    publicacion = ficha.publicaciones.filter(
        tipo=Publicacion.Tipo.ADOPCION, estado=Publicacion.Estado.VIGENTE
    ).first()
    return publicacion.telefono_visible if publicacion else ""


@cuenta_habilitada
def elegir(request, postulacion_pk):
    """Confirmar a quién se elige para adoptar: GET pregunta, POST elige (CU-29)."""
    postulacion = get_object_or_404(
        Postulacion.objects.select_related("ficha", "usuario"),
        pk=postulacion_pk,
        tipo=Postulacion.Tipo.ADOPCION,
    )
    ficha = postulacion.ficha
    if not permisos.puede_ver(request.user, ficha):
        raise Http404
    if not eleccion.puede_elegir(request.user, ficha):
        raise PermissionDenied
    datos = request.POST if request.method == "POST" else None
    form = ElegirForm(datos, initial={"telefono": _telefono_publicado(ficha)})
    error = None
    if form.is_valid():
        try:
            eleccion.elegir_adoptante(postulacion, request.user, form.cleaned_data["telefono"])
        except eleccion.EleccionNoPermitida as motivo:
            error = str(motivo)
        else:
            return redirect("adopcion:postulantes", ficha_pk=ficha.pk)
    contexto = {"postulacion": postulacion, "ficha": ficha, "form": form, "error": error}
    return render(request, "adopcion/elegir.html", contexto)
