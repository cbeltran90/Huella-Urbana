from constance import config
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse

from . import servicios
from .decoradores import cuenta_habilitada
from .forms import DomicilioForm, ReenviarConfirmacionForm, RegistroForm
from .models import Domicilio, EstadoCuenta

MENSAJE_ERROR_GENERAL = "Error al crear cuenta. Revisar nombre de usuario y correo."


def registro(request):
    if request.user.is_authenticated:
        return redirect("core:inicio")
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    usuario = form.save()
            except IntegrityError:
                # Dos envíos a la vez: el segundo choca con el nombre o el correo del primero.
                form.add_error(None, MENSAJE_ERROR_GENERAL)
            else:
                servicios.enviar_correo_confirmacion(usuario, request)
                return redirect("cuentas:registro_listo")
    else:
        form = RegistroForm()
    return render(request, "cuentas/registro.html", {"form": form})


def registro_listo(request):
    return render(request, "cuentas/registro_listo.html")


def confirmar(request, token):
    usuario = servicios.usuario_de_token(token)
    if usuario is None or usuario.estado_cuenta == EstadoCuenta.ELIMINADA:
        return render(request, "cuentas/confirmar_fallida.html", status=400)
    if usuario.estado_cuenta == EstadoCuenta.PENDIENTE:
        usuario.estado_cuenta = EstadoCuenta.ACTIVA
        usuario.save(update_fields=["estado_cuenta"])
    return render(request, "cuentas/confirmar_listo.html")


def reenviar_confirmacion(request):
    if request.method == "POST":
        form = ReenviarConfirmacionForm(request.POST)
        if form.is_valid():
            servicios.reenviar_confirmacion(form.cleaned_data["email"], request)
            return redirect("cuentas:reenvio_listo")
    else:
        form = ReenviarConfirmacionForm()
    return render(request, "cuentas/reenviar.html", {"form": form})


def reenvio_listo(request):
    return render(request, "cuentas/reenvio_listo.html")


@cuenta_habilitada
def domicilio(request):
    if request.method == "POST":
        form = DomicilioForm(request.POST)
        if form.is_valid():
            try:
                servicios.guardar_domicilio(request.user, form.punto())
            except servicios.DomicilioInvalido as error:
                form.add_error(None, str(error))
            else:
                return redirect(f"{reverse('cuentas:domicilio')}?guardado=1")
    else:
        form = DomicilioForm()
    # Al navegador solo llega el punto desplazado: el exacto nunca sale del servidor.
    registro = Domicilio.objects.filter(usuario=request.user).first()
    centro = None
    if registro:
        centro = {"lat": registro.ubicacion_desplazada.y, "lng": registro.ubicacion_desplazada.x}
    contexto = {
        "form": form,
        "centro": centro,
        "radio": config.RADIO_DOMICILIO_METROS,
        "guardado": request.GET.get("guardado") == "1",
    }
    return render(request, "cuentas/domicilio.html", contexto)
