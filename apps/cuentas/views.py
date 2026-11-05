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
    CambioCorreoForm,
    DatosHogarForm,
    DomicilioForm,
    NombreUsuarioForm,
    PerfilAdoptanteForm,
    ReenviarConfirmacionForm,
    RegistroForm,
)
from .models import Domicilio, EstadoCuenta, PerfilAdoptante

MENSAJE_ERROR_GENERAL = "Error al crear cuenta. Revisar nombre de usuario y correo."
MENSAJE_ENVIO_FALLIDO = "No pudimos enviar el correo. Probá de nuevo en unos minutos"


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
    domicilio = Domicilio.objects.filter(usuario=request.user).first()
    contexto = {
        "domicilio": domicilio,
        "tiene_domicilio": domicilio is not None,
        "hogar_completo": domicilio is not None and domicilio.hogar_completo,
        "tiene_perfil_adoptante": PerfilAdoptante.objects.filter(usuario=request.user).exists(),
        "guardado": request.GET.get("guardado") == "1",
    }
    return render(request, "cuentas/perfil.html", contexto)


@cuenta_habilitada
def datos_hogar(request):
    # Quien viene del perfil de adopción o del de tránsito vuelve allí.
    destinos = {"adopcion": "cuentas:perfil_adoptante", "transito": "transito:perfil_transito"}
    volver_url = reverse(destinos.get(request.GET.get("volver"), "cuentas:perfil"))
    domicilio = Domicilio.objects.filter(usuario=request.user).first()
    if domicilio is None:
        # Los datos del hogar cuelgan del domicilio: primero hay que registrarlo.
        contexto = {"sin_domicilio": True, "volver_url": volver_url}
        return render(request, "cuentas/datos_hogar.html", contexto)
    if request.method == "POST":
        form = DatosHogarForm(request.POST, instance=domicilio)
        if form.is_valid():
            form.save()
            return redirect(f"{volver_url}?guardado=1")
    else:
        form = DatosHogarForm(instance=domicilio)
    return render(request, "cuentas/datos_hogar.html", {"form": form, "volver_url": volver_url})


@cuenta_habilitada
def perfil_adoptante(request):
    faltantes = []
    if request.method == "POST":
        form = PerfilAdoptanteForm(request.POST)
        if form.is_valid():
            try:
                servicios.guardar_perfil_adoptante(
                    request.user, form.cleaned_data["experiencia_previa"]
                )
            except servicios.PerfilAdoptanteIncompleto as error:
                faltantes = error.faltantes
            except servicios.PerfilAdoptanteInvalido as error:
                form.add_error("experiencia_previa", str(error))
            else:
                return redirect(f"{reverse('cuentas:perfil')}?guardado=1")
    else:
        perfil = PerfilAdoptante.objects.filter(usuario=request.user).first()
        inicial = perfil.experiencia_previa if perfil else ""
        form = PerfilAdoptanteForm(initial={"experiencia_previa": inicial})
    domicilio = Domicilio.objects.filter(usuario=request.user).first()
    contexto = {
        "form": form,
        "faltantes": faltantes,
        "domicilio": domicilio,
        "hogar_completo": domicilio is not None and domicilio.hogar_completo,
        "puede_postularse": servicios.puede_postularse_a_adoptar(request.user),
        "max_caracteres": servicios.MAX_EXPERIENCIA_PREVIA,
        "guardado": request.GET.get("guardado") == "1",
    }
    return render(request, "cuentas/perfil_adoptante.html", contexto)


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


@cuenta_habilitada
def cambiar_correo(request):
    if request.method == "POST":
        form = CambioCorreoForm(request.POST)
        if form.is_valid():
            try:
                enviado = servicios.solicitar_cambio_correo(
                    request.user, form.cleaned_data["email"], request
                )
            except servicios.CambioCorreoInvalido as error:
                form.add_error("email", str(error))
            else:
                if enviado:
                    return redirect("cuentas:cambiar_correo_enviado")
                form.add_error(None, MENSAJE_ENVIO_FALLIDO)
    else:
        form = CambioCorreoForm()
    return render(request, "cuentas/cambiar_correo.html", {"form": form})


@cuenta_habilitada
def cambiar_correo_enviado(request):
    return render(request, "cuentas/cambiar_correo_enviado.html")
