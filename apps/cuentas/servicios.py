"""Reglas de cuentas que usan otras partes del sistema."""

import logging
from datetime import timedelta

from constance import config
from django.contrib.gis.geos import Point
from django.core import signing
from django.core.cache import caches
from django.core.mail import send_mail
from django.db import IntegrityError, models, transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from . import geo
from .models import (
    CAMPOS_HOGAR,
    MAX_EXPERIENCIA_PREVIA,
    Domicilio,
    EstadoCuenta,
    PerfilAdoptante,
    Rol,
    Sancion,
    Usuario,
    hash_email,
    normalizar_email,
)

logger = logging.getLogger(__name__)

SAL_CONFIRMACION = "cuentas.confirmar-correo"
DIAS_VIGENCIA_ENLACE = 1
ESPERA_REENVIO_SEGUNDOS = 5 * 60
ESPERA_RECUPERACION_SEGUNDOS = 5 * 60
SAL_CAMBIO_CORREO = "cuentas.cambiar-correo"
DIAS_VIGENCIA_CAMBIO_CORREO = 1
ESPERA_CAMBIO_CORREO_SEGUNDOS = 5 * 60

MENSAJE_CORREO_USADO = "El correo electrónico ingresado ya se encuentra registrado"
MENSAJE_CORREO_SUSPENDIDO = "Correo con suspensión permanente"
MENSAJE_CORREO_IGUAL = "Ese ya es el correo de tu cuenta"
MENSAJE_CAMBIO_RECIENTE = "Ya te enviamos un enlace. Esperá unos minutos para pedir otro"
MENSAJE_ENLACE_CORREO_INVALIDO = "El enlace está dañado, venció o ya se usó"
MENSAJE_CUENTA_SIN_CAMBIO_DE_CORREO = "Tu cuenta no puede cambiar el correo en este momento"


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

    Cuenta las anteriores de la misma persona (por cuenta o por correo) que no se levantaron. El
    moderador puede elegir la permanente igual: extensión 3A de CU-59.
    """
    anteriores = Sancion.objects.filter(
        models.Q(usuario=usuario) | models.Q(email_hash=usuario.email_hash),
        revocada_en__isnull=True,
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


def guardar_domicilio(usuario, punto):
    """Guarda el domicilio a partir del punto que la persona marcó en el mapa.

    El punto exacto queda privado. El desplazado (a menos de RADIO_DOMICILIO_METROS) es el
    único que se muestra: se calcula una sola vez y se conserva si el punto no cambia.
    Lanza DomicilioInvalido si el punto está fuera de la zona.
    """
    punto = _punto_valido(punto)
    with transaction.atomic():
        domicilio = Domicilio.objects.select_for_update().filter(usuario=usuario).first()
        if domicilio is None:
            domicilio = Domicilio(usuario=usuario)
        if domicilio.pk is None or not domicilio.ubicacion.equals_exact(punto, 1e-9):
            lon, lat = geo.desplazar(punto.x, punto.y, config.RADIO_DOMICILIO_METROS)
            domicilio.ubicacion = punto
            domicilio.ubicacion_desplazada = Point(lon, lat, srid=4326)
        domicilio.save()
    return domicilio


class CambioCorreoInvalido(Exception):
    """No se puede pedir o aplicar el cambio de correo. El mensaje está pensado para mostrarse."""


def validar_correo_nuevo(usuario, email):
    """El correo nuevo normalizado, o CambioCorreoInvalido si no se puede usar.

    Las reglas son las del registro: no puede estar en uso ni tener una suspensión
    permanente. Además, no puede ser el mismo que ya tiene la cuenta.
    """
    email = normalizar_email(email)
    if email == usuario.email:
        raise CambioCorreoInvalido(MENSAJE_CORREO_IGUAL)
    if Usuario.objects.filter(email__iexact=email).exclude(pk=usuario.pk).exists():
        raise CambioCorreoInvalido(MENSAJE_CORREO_USADO)
    if correo_con_suspension_permanente(email):
        raise CambioCorreoInvalido(MENSAJE_CORREO_SUSPENDIDO)
    return email


def crear_token_cambio_correo(usuario, email_nuevo):
    """Enlace firmado con la cuenta, su correo actual y el nuevo.

    Al aplicarse el cambio el correo actual deja de coincidir, así que sirve una sola vez.
    """
    return signing.dumps([usuario.pk, usuario.email, email_nuevo], salt=SAL_CAMBIO_CORREO)


def solicitar_cambio_correo(usuario, email_nuevo, request):
    """Envía el enlace de confirmación al correo nuevo (CU-03, extensión 4D1).

    El correo de la cuenta no cambia hasta que se abre el enlace. Devuelve False si no se
    pudo enviar. Lanza CambioCorreoInvalido si el correo no sirve o se pidió hace poco.
    """
    email_nuevo = validar_correo_nuevo(usuario, email_nuevo)
    clave = f"cambio-correo:{usuario.pk}"
    if not caches["reenvios"].add(clave, True, ESPERA_CAMBIO_CORREO_SEGUNDOS):
        raise CambioCorreoInvalido(MENSAJE_CAMBIO_RECIENTE)
    token = crear_token_cambio_correo(usuario, email_nuevo)
    ruta = reverse("cuentas:confirmar_correo", args=[token])
    contexto = {
        "usuario": usuario,
        "enlace": request.build_absolute_uri(ruta),
        "dias": DIAS_VIGENCIA_CAMBIO_CORREO,
    }
    try:
        send_mail(
            "Confirmá tu nuevo correo en Huella Urbana",
            render_to_string("cuentas/correo_cambio_correo.txt", contexto),
            None,
            [email_nuevo],
        )
    except OSError:
        logger.exception("No se pudo enviar el correo de cambio de correo (usuario %s)", usuario.pk)
        # Si no salió el correo, la persona puede volver a intentar sin esperar.
        caches["reenvios"].delete(clave)
        return False
    return True


def confirmar_cambio_correo(token):
    """Aplica el cambio de correo de un enlace (CU-03, extensión 4D2) y devuelve la cuenta.

    Lanza CambioCorreoInvalido si el enlace está alterado, venció o ya se usó, si la cuenta
    está suspendida o si el correo ya lo tomó otra persona.
    """
    try:
        pk, actual, nuevo = signing.loads(
            token,
            salt=SAL_CAMBIO_CORREO,
            max_age=DIAS_VIGENCIA_CAMBIO_CORREO * 24 * 60 * 60,
        )
    except (signing.BadSignature, ValueError):
        raise CambioCorreoInvalido(MENSAJE_ENLACE_CORREO_INVALIDO) from None
    with transaction.atomic():
        # Se bloquea la cuenta para que dos aperturas del enlace no se pisen.
        usuario = Usuario.objects.select_for_update().filter(pk=pk).first()
        if usuario is None or usuario.email != actual:
            raise CambioCorreoInvalido(MENSAJE_ENLACE_CORREO_INVALIDO)
        if usuario.estado_cuenta != EstadoCuenta.ACTIVA or sancion_vigente(usuario) is not None:
            raise CambioCorreoInvalido(MENSAJE_CUENTA_SIN_CAMBIO_DE_CORREO)
        usuario.email = validar_correo_nuevo(usuario, nuevo)
        try:
            usuario.save(update_fields=["email", "email_hash"])
        except IntegrityError as error:
            raise CambioCorreoInvalido(MENSAJE_CORREO_USADO) from error
    logger.info("Cambio de correo confirmado (usuario %s)", usuario.pk)
    return usuario


ETIQUETA_EXPERIENCIA = "Experiencia previa con animales"
MENSAJE_EXPERIENCIA_LARGA = (
    f"La experiencia previa admite hasta {MAX_EXPERIENCIA_PREVIA} caracteres"
)


class PerfilAdoptanteInvalido(ValueError):
    """El perfil de adoptante no se puede guardar. El mensaje está pensado para mostrarse."""


class PerfilAdoptanteIncompleto(PerfilAdoptanteInvalido):
    """Faltan datos obligatorios: "faltantes" dice, en palabras, qué hay que completar."""

    def __init__(self, faltantes):
        self.faltantes = faltantes
        super().__init__("Faltan datos: " + ", ".join(faltantes))


def _etiqueta_hogar(campo):
    texto = str(Domicilio._meta.get_field(campo).verbose_name)
    return texto[:1].upper() + texto[1:]


def datos_faltantes_adoptante(usuario, experiencia_previa):
    """Lo que falta para tener completo el perfil de hogar y familia, en palabras."""
    faltantes = []
    domicilio = Domicilio.objects.filter(usuario=usuario).first()
    if domicilio is None:
        faltantes.append("Domicilio")
        faltantes.extend(_etiqueta_hogar(campo) for campo in CAMPOS_HOGAR)
    else:
        faltantes.extend(_etiqueta_hogar(campo) for campo in domicilio.hogar_faltante())
    if not (experiencia_previa or "").strip():
        faltantes.append(ETIQUETA_EXPERIENCIA)
    return faltantes


def guardar_perfil_adoptante(usuario, experiencia_previa):
    """Guarda el perfil de hogar y familia solo si está completo (CU-05, 5A).

    Si falta algo no guarda nada y lanza PerfilAdoptanteIncompleto con lo que falta.
    Si ya había un perfil, lo actualiza.
    """
    experiencia = (experiencia_previa or "").strip()
    faltantes = datos_faltantes_adoptante(usuario, experiencia)
    if faltantes:
        raise PerfilAdoptanteIncompleto(faltantes)
    if len(experiencia) > MAX_EXPERIENCIA_PREVIA:
        raise PerfilAdoptanteInvalido(MENSAJE_EXPERIENCIA_LARGA)
    perfil, _ = PerfilAdoptante.objects.update_or_create(
        usuario=usuario, defaults={"experiencia_previa": experiencia}
    )
    return perfil


def puede_postularse_a_adoptar(usuario):
    """True si la persona puede postularse para adoptar (CU-28).

    Hace falta tener el perfil de hogar y familia guardado, los datos del hogar completos y
    una cuenta activa sin sanción vigente: con una sanción queda con permisos de visitante.
    """
    if not usuario.is_authenticated or usuario.estado_cuenta != EstadoCuenta.ACTIVA:
        return False
    if esta_suspendido(usuario):
        return False
    domicilio = Domicilio.objects.filter(usuario=usuario).first()
    return (
        domicilio is not None
        and domicilio.hogar_completo
        and PerfilAdoptante.objects.filter(usuario=usuario).exists()
    )
