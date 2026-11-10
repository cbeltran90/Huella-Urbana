from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.cuentas.decoradores import cuenta_habilitada
from apps.cuentas.models import Domicilio
from apps.fichas import permisos
from apps.fichas.models import FichaAnimal

from . import postulaciones, servicios
from .forms import PerfilTransitoForm, PostulacionForm
from .models import PerfilTransito


def _inicial(perfil, estimado):
    """Valores con los que arranca el formulario."""
    if perfil is None:
        inicial = {"disponibilidad": "True"}
        if estimado is not None:
            inicial["cupo_declarado"] = estimado
        return inicial
    return {
        "especies": perfil.especies,
        "tamano_maximo": perfil.tamano_maximo,
        "duracion_maxima_dias": perfil.duracion_maxima_dias,
        "acepta_medicacion": perfil.acepta_medicacion,
        "acepta_conducta": perfil.acepta_conducta,
        "disponibilidad": str(perfil.disponibilidad),
        "pausa_hasta": perfil.pausa_hasta.isoformat() if perfil.pausa_hasta else "",
        "cupo_declarado": perfil.cupo_declarado,
    }


@cuenta_habilitada
def perfil_transito(request):
    faltantes = []
    excede_estimado = False
    domicilio = Domicilio.objects.filter(usuario=request.user).first()
    estimado = servicios.cupo_estimado(domicilio)
    if request.method == "POST":
        form = PerfilTransitoForm(request.POST)
        if form.is_valid():
            try:
                servicios.guardar_perfil_transito(request.user, **form.cleaned_data)
            except servicios.PerfilTransitoIncompleto as error:
                faltantes = error.faltantes
            except servicios.PerfilTransitoInvalido as error:
                for campo, mensaje in error.errores.items():
                    form.add_error(campo, mensaje)
            except servicios.CupoSuperaEstimado:
                excede_estimado = True
            else:
                return redirect(f"{reverse('cuentas:perfil')}?guardado=1")
    else:
        perfil = PerfilTransito.objects.filter(usuario=request.user).first()
        form = PerfilTransitoForm(initial=_inicial(perfil, estimado))
    contexto = {
        "form": form,
        "faltantes": faltantes,
        "domicilio": domicilio,
        "hogar_completo": domicilio is not None and domicilio.hogar_completo,
        "cupo_estimado": estimado,
        "excede_estimado": excede_estimado,
        "es_hogar_de_transito": servicios.es_hogar_de_transito(request.user),
        "guardado": request.GET.get("guardado") == "1",
    }
    return render(request, "transito/perfil_transito.html", contexto)


@cuenta_habilitada
def desactivar_perfil_transito(request):
    if not servicios.es_hogar_de_transito(request.user):
        return redirect("transito:perfil_transito")
    if request.method == "POST":
        try:
            servicios.desactivar_perfil_transito(request.user)
        except servicios.DesactivacionNoPermitida:
            pass
        else:
            return redirect(f"{reverse('cuentas:perfil')}?guardado=1")
    contexto = {"no_permitido": servicios.tiene_animales_a_cargo(request.user)}
    return render(request, "transito/desactivar_perfil.html", contexto)


@cuenta_habilitada
def postular(request, ficha_pk):
    """Postularse como hogar de tránsito a una ficha en adopción."""
    ficha = get_object_or_404(FichaAnimal, pk=ficha_pk)
    if not permisos.puede_ver(request.user, ficha):
        raise Http404
    motivo = postulaciones.motivo_para_no_postularse(request.user, ficha)
    form = PostulacionForm(request.POST or None)
    if motivo is None and form.is_valid():
        try:
            postulaciones.postular_transito(request.user, ficha, form.cleaned_data["contacto"])
        except postulaciones.PostulacionNoPermitida as error:
            motivo = (error.codigo, error.mensaje)
        except postulaciones.ContactoInvalido as error:
            form.add_error("contacto", str(error))
        else:
            return redirect(f"{reverse('fichas:detalle', args=[ficha.pk])}?postulado=1")
    contexto = {
        "ficha": ficha,
        "form": form,
        "motivo": motivo,
        "advertencias": postulaciones.advertencias_de_postulacion(request.user, ficha),
    }
    return render(request, "transito/postular.html", contexto)
