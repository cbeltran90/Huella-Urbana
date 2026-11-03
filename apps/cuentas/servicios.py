"""Reglas de cuentas que usan otras partes del sistema."""

import logging
from datetime import timedelta

from constance import config
from django.contrib.gis.geos import Point
from django.core import signing
from django.core.cache import caches
from django.core.mail import send_mail
from django.db import models, transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from . import geo
from .models import Domicilio, EstadoCuenta, Rol, Sancion, Usuario, hash_email, normalizar_email

logger = logging.getLogger(__name__)

SAL_CONFIRMACION = "cuentas.confirmar-correo"
DIAS_VIGENCIA_ENLACE = 1
ESPERA_REENVIO_SEGUNDOS = 5 * 60
ESPERA_RECUPERACION_SEGUNDOS = 5 * 60


class SancionNoPermitida(Exception):
    """No se puede aplicar o levantar la sanción. El mensaje está pensado para mostrarse."""


def _puede_moderar(usuario):
    return (
        bool(usuario)
        and usuario.is_authenticated
        and usuario.rol
        in (
            Rol.MODERADOR,
            Rol.ADMINISTRADOR,
        )
    )


def sancion_vigente(usuario):
    """La sanción que rige hoy para el usuario, o None.

    Un visitante no tiene. Si hubiera más de una, devuelve primero la permanente.
    """
    if not usuario.is_authenticated:
        return None
    return (
        Sancion.objects.vigentes()
        .filter(usuario=usuario)
        .order_by(models.F("fin").desc(nulls_first=True))
        .first()
    )


def esta_suspendido(usuario):
    """True si la cuenta tiene una sanción vigente: queda con permisos de visitante."""
    return sancion_vigente(usuario) is not None


def correo_con_suspension_permanente(email):
    """True si el correo tiene una suspensión permanente vigente (aunque la cuenta se haya
    eliminado): impide volver a registrarse con él."""
    return (
        Sancion.objects.vigentes()
        .filter(tipo=Sancion.Tipo.PERMANENTE, email_hash=hash_email(email))
        .exists()
    )


def tipo_sugerido(usuario):
    """Qué sanción corresponde por defecto: temporal la primera vez, permanente después.

    Cuenta las anteriores de la misma persona (por correo) que no se levantaron. El
    moderador puede elegir la permanente igual: extensión 3A de CU-59.
    """
    anteriores = Sancion.objects.filter(
        email_hash=usuario.email_hash, revocada_en__isnull=True
    ).exists()
    return Sancion.Tipo.PERMANENTE if anteriores else Sancion.Tipo.TEMPORAL


def verificar_sancion(usuario, motivo, aplicada_por):
    """Comprueba que se pueda sancionar a la cuenta; si no, lanza SancionNoPermitida."""
    if not _puede_moderar(aplicada_por):
        raise SancionNoPermitida("Solo un moderador o un administrador puede sancionar")
    if usuario.pk == aplicada_por.pk:
        raise SancionNoPermitida("No podés sancionar tu propia cuenta")
    if usuario.rol == Rol.ADMINISTRADOR and aplicada_por.rol != Rol.ADMINISTRADOR:
        raise SancionNoPermitida("Un moderador no puede sancionar a un administrador")
    if not (motivo or "").strip():
        raise SancionNoPermitida("El motivo es obligatorio")
    if sancion_vigente(usuario) is not None:
        raise SancionNoPermitida("La cuenta ya tiene una sanción vigente")


def sancionar(usuario, tipo, motivo, aplicada_por):
    """Suspende la cuenta. Solo moderadores y administradores (CU-59).

    La temporal dura "DIAS_PRIMERA_SUSPENSION" días; la permanente no vence.
    """
    with transaction.atomic():
        # Se bloquea la cuenta para que dos moderadores no sancionen a la vez.
        Usuario.objects.select_for_update().get(pk=usuario.pk)
        verificar_sancion(usuario, motivo, aplicada_por)
        inicio = timezone.now()
        fin = None
        if tipo == Sancion.Tipo.TEMPORAL:
            fin = inicio + timedelta(days=config.DIAS_PRIMERA_SUSPENSION)
        return Sancion.objects.create(
            usuario=usuario,
            email_hash=usuario.email_hash,
            tipo=tipo,
            motivo=motivo.strip(),
            inicio=inicio,
            fin=fin,
            aplicada_por=aplicada_por,
        )


def levantar_sancion(sancion, levantada_por):
    """Deja sin efecto una sanción vigente. Solo moderadores y administradores."""
    if not _puede_moderar(levantada_por):
        raise SancionNoPermitida("Solo un moderador o un administrador puede levantar sanciones")
    if not Sancion.objects.vigentes().filter(pk=sancion.pk).exists():
        raise SancionNoPermitida("La sanción ya no está vigente")
    sancionado = sancion.usuario
    if (
        sancionado
        and sancionado.rol == Rol.ADMINISTRADOR
        and levantada_por.rol != Rol.ADMINISTRADOR
    ):
        raise SancionNoPermitida("Un moderador no puede levantar la sanción de un administrador")
    sancion.revocada_en = timezone.now()
    sancion.revocada_por = levantada_por
    sancion.save(update_fields=["revocada_en", "revocada_por"])
    return sancion


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


def reenviar_confirmacion(email, request):
    """Reenvía el enlace a una cuenta pendiente (CU-01 5C).

    No devuelve nada a propósito: la vista responde igual exista o no la cuenta.
    """
    usuario = Usuario.objects.filter(
        email=normalizar_email(email), estado_cuenta=EstadoCuenta.PENDIENTE
    ).first()
    if usuario is None:
        return
    if not caches["reenvios"].add(
        f"reenvio-confirmacion:{usuario.pk}", True, ESPERA_REENVIO_SEGUNDOS
    ):
        return
    enviar_correo_confirmacion(usuario, request)


MENSAJE_FUERA_DE_ZONA = "El domicilio tiene que estar en Ushuaia y alrededores"


class DomicilioInvalido(ValueError):
    """El domicilio no se puede guardar. El mensaje está pensado para mostrarse."""


def _punto_valido(punto):
    """El punto en coordenadas 4326 (longitud, latitud), o DomicilioInvalido."""
    if not isinstance(punto, Point) or punto.empty:
        raise DomicilioInvalido("Falta indicar el domicilio en el mapa")
    if punto.srid is None:
        punto = Point(punto.x, punto.y, srid=4326)
    elif punto.srid != 4326:
        punto = punto.transform(4326, clone=True)
    if not geo.en_zona(punto.x, punto.y):
        raise DomicilioInvalido(MENSAJE_FUERA_DE_ZONA)
    return punto


def guardar_domicilio(usuario, punto, direccion=None):
    """Guarda o cambia el domicilio del usuario y devuelve el registro (CU-03).

    "punto" es el lugar exacto. Se calcula un punto desplazado a menos de
    RADIO_DOMICILIO_METROS, que es el único que se puede mostrar. Se calcula una sola vez:
    si el punto no cambió, se conserva el desplazado que ya tenía (RNF3).
    "direccion" en None deja la dirección escrita como estaba: otros módulos solo pasan
    el punto.
    """
    punto = _punto_valido(punto)
    if direccion is not None:
        direccion = direccion.strip()
        maximo = Domicilio._meta.get_field("direccion").max_length
        if len(direccion) > maximo:
            raise DomicilioInvalido("La dirección es demasiado larga")
    with transaction.atomic():
        domicilio = Domicilio.objects.select_for_update().filter(usuario=usuario).first()
        if domicilio is None:
            domicilio = Domicilio(usuario=usuario)
        if domicilio.pk is None or not domicilio.ubicacion.equals_exact(punto, 1e-9):
            lon, lat = geo.desplazar(punto.x, punto.y, config.RADIO_DOMICILIO_METROS)
            domicilio.ubicacion = punto
            domicilio.ubicacion_desplazada = Point(lon, lat, srid=4326)
        if direccion is not None:
            domicilio.direccion = direccion
        domicilio.save()
    return domicilio
