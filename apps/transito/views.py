from django.shortcuts import redirect, render
from django.urls import reverse

from apps.cuentas.decoradores import cuenta_habilitada
from apps.cuentas.models import Domicilio

from . import servicios
from .forms import PerfilTransitoForm
from .models import PerfilTransito


def _inicial(perfil):
    """Valores con los que arranca el formulario."""
    if perfil is None:
        return {"disponibilidad": "True"}
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
            else:
                return redirect(f"{reverse('cuentas:perfil')}?guardado=1")
    else:
        perfil = PerfilTransito.objects.filter(usuario=request.user).first()
        form = PerfilTransitoForm(initial=_inicial(perfil))
    domicilio = Domicilio.objects.filter(usuario=request.user).first()
    contexto = {
        "form": form,
        "faltantes": faltantes,
        "domicilio": domicilio,
        "hogar_completo": domicilio is not None and domicilio.hogar_completo,
        "es_hogar_de_transito": servicios.es_hogar_de_transito(request.user),
        "guardado": request.GET.get("guardado") == "1",
    }
    return render(request, "transito/perfil_transito.html", contexto)
