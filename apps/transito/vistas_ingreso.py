"""Pantallas para registrar el ingreso al hogar de tránsito o cancelar la entrega (CU-26)."""

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from apps.cuentas.decoradores import cuenta_habilitada
from apps.fichas import permisos
from apps.fichas.models import FichaAnimal

from . import ingreso

SANIDAD = ("vacunado", "castrado", "desparasitado")


def _ficha_para_entregar(request, ficha_pk):
    """La ficha, si quien entra puede registrar el ingreso o cancelar la entrega."""
    ficha = get_object_or_404(FichaAnimal, pk=ficha_pk)
    if not permisos.puede_ver(request.user, ficha):
        raise Http404
    if not ingreso.puede_registrar_ingreso(request.user, ficha):
        raise PermissionDenied
    return ficha


@cuenta_habilitada
def registrar_ingreso(request, ficha_pk):
    """Confirmar que la mascota llegó al hogar elegido: GET pregunta, POST registra."""
    ficha = _ficha_para_entregar(request, ficha_pk)
    elegida = ingreso.hogar_elegido(ficha)
    error = None if elegida else ingreso.MENSAJE_SIN_HOGAR
    if request.method == "POST" and error is None:
        # Una casilla sin marcar no viaja en el POST.
        sanidad = {campo: campo in request.POST for campo in SANIDAD}
        try:
            ingreso.registrar_ingreso(ficha, request.user, **sanidad)
        except ingreso.IngresoNoPermitido as motivo:
            error = str(motivo)
        else:
            # Quien la entregó deja de tenerla a cargo: si la ficha es privada, ya no la ve.
            if permisos.puede_ver(request.user, ficha):
                return redirect("fichas:detalle", pk=ficha.pk)
            return redirect("publicaciones:disponibles")
    contexto = {"ficha": ficha, "elegida": elegida, "error": error}
    return render(request, "transito/registrar_ingreso.html", contexto)


@cuenta_habilitada
def cancelar_entrega(request, ficha_pk):
    """Cancelar la entrega al hogar elegido (1A): GET pregunta, POST cancela."""
    ficha = _ficha_para_entregar(request, ficha_pk)
    elegida = ingreso.hogar_elegido(ficha)
    error = None if elegida else ingreso.MENSAJE_SIN_HOGAR
    if request.method == "POST" and error is None:
        try:
            ingreso.cancelar_entrega(ficha, request.user)
        except ingreso.IngresoNoPermitido as motivo:
            error = str(motivo)
        else:
            return redirect("fichas:detalle", pk=ficha.pk)
    contexto = {"ficha": ficha, "elegida": elegida, "error": error}
    return render(request, "transito/cancelar_entrega.html", contexto)
