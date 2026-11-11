from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.cuentas.decoradores import cuenta_habilitada
from apps.fichas import permisos
from apps.fichas.models import FichaAnimal
from apps.transito.forms import PostulacionForm

from . import postulaciones


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
