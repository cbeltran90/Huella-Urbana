"""Reglas de cuentas que usan otras partes del sistema."""

import logging

from django.core import signing
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from .models import Usuario

logger = logging.getLogger(__name__)

SAL_CONFIRMACION = "cuentas.confirmar-correo"
DIAS_VIGENCIA_ENLACE = 1


def correo_con_suspension_permanente(email):
    """True si el correo tiene una suspensión permanente vigente.

    Todavía no existe el modelo Sancion: hasta entonces nadie está suspendido.
    """
    return False


def crear_token_confirmacion(usuario):
    return signing.dumps(usuario.pk, salt=SAL_CONFIRMACION)


def usuario_de_token(token):
    """El usuario de un enlace de confirmación, o None si está alterado o venció."""
    try:
        pk = signing.loads(
            token,
            salt=SAL_CONFIRMACION,
            max_age=DIAS_VIGENCIA_ENLACE * 24 * 60 * 60,
        )
    except signing.BadSignature:
        return None
    return Usuario.objects.filter(pk=pk).first()


def enviar_correo_confirmacion(usuario, request):
    """Envía el enlace para confirmar la cuenta. Devuelve False si no se pudo enviar."""
    ruta = reverse("cuentas:confirmar", args=[crear_token_confirmacion(usuario)])
    contexto = {
        "usuario": usuario,
        "enlace": request.build_absolute_uri(ruta),
        "dias": DIAS_VIGENCIA_ENLACE,
    }
    try:
        send_mail(
            "Confirmá tu cuenta en Huella Urbana",
            render_to_string("cuentas/correo_confirmacion.txt", contexto),
            None,
            [usuario.email],
        )
    except OSError:
        logger.exception("No se pudo enviar el correo de confirmación (usuario %s)", usuario.pk)
        return False
    return True
