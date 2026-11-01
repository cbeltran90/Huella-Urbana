from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render

from . import servicios
from .forms import RegistroForm
from .models import EstadoCuenta

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
