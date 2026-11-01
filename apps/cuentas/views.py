from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render

from .forms import RegistroForm

MENSAJE_ERROR_GENERAL = "Error al crear cuenta. Revisar nombre de usuario y correo."


def registro(request):
    if request.user.is_authenticated:
        return redirect("core:inicio")
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
            except IntegrityError:
                # Dos envíos a la vez: el segundo choca con el nombre o el correo del primero.
                form.add_error(None, MENSAJE_ERROR_GENERAL)
            else:
                return redirect("cuentas:registro_listo")
    else:
        form = RegistroForm()
    return render(request, "cuentas/registro.html", {"form": form})


def registro_listo(request):
    return render(request, "cuentas/registro_listo.html")
