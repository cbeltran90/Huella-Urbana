from constance import config
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.urls import reverse

from . import servicios
from .decoradores import cuenta_habilitada
from .forms import (
    CambioContrasenaForm,
    DomicilioForm,
    NombreUsuarioForm,
    ReenviarConfirmacionForm,
    RegistroForm,
)
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
                return redirect(f"{reverse('cuentas:perfil')}?guardado=1")
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
    }
    return render(request, "cuentas/domicilio.html", contexto)


@cuenta_habilitada
def perfil(request):
    contexto = {
        "tiene_domicilio": Domicilio.objects.filter(usuario=request.user).exists(),
        "guardado": request.GET.get("guardado") == "1",
    }
    return render(request, "cuentas/perfil.html", contexto)


@cuenta_habilitada
def editar_perfil(request):
    if request.method == "POST":
        form = NombreUsuarioForm(request.POST, usuario=request.user)
        if form.is_valid():
            try:
                form.save()
            except ValidationError as error:
                form.add_error("nombre_usuario", error)
            else:
                return redirect(f"{reverse('cuentas:perfil')}?guardado=1")
    else:
        form = NombreUsuarioForm(
            initial={"nombre_usuario": request.user.nombre_usuario}, usuario=request.user
        )
    return render(request, "cuentas/editar_perfil.html", {"form": form})


@cuenta_habilitada
def cambiar_contrasena(request):
    if request.method == "POST":
        form = CambioContrasenaForm(request.user, request.POST)
        if form.is_valid():
            usuario = form.save()
            # Mantiene abierta la sesión actual; las demás quedan cerradas.
            update_session_auth_hash(request, usuario)
            return redirect(f"{reverse('cuentas:perfil')}?guardado=1")
    else:
        form = CambioContrasenaForm(request.user)
    return render(request, "cuentas/cambiar_contrasena.html", {"form": form})


def confirmar_correo(request, token):
    try:
        servicios.confirmar_cambio_correo(token)
    except servicios.CambioCorreoInvalido as error:
        return render(request, "cuentas/correo_fallido.html", {"motivo": str(error)}, status=400)
    return render(request, "cuentas/correo_confirmado.html")
