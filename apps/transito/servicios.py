"""Reglas del hogar de tránsito que usan otras partes del sistema."""

from constance import config
from django.utils import timezone

from apps.cuentas.models import CAMPOS_HOGAR, Domicilio, EstadoCuenta, TipoVivienda
from apps.cuentas.servicios import esta_suspendido
from apps.fichas.models import FichaAnimal

from .models import MAX_CUPO_DECLARADO, PerfilTransito

# Tope provisorio de la duración máxima que puede declarar un hogar.
MAX_DURACION_MAXIMA_DIAS = 365

# Cupo que el sistema sugiere según la vivienda. Es solo una sugerencia: la
# persona declara el número final. Valores provisorios; para cambiarlos se tocan acá.
CUPO_POR_VIVIENDA = {
    TipoVivienda.CASA: 3,
    TipoVivienda.DEPARTAMENTO: 1,
    TipoVivienda.OTRA: 1,
}
CUPO_EXTRA_POR_PATIO = 2
MAX_CUPO_ESTIMADO = 5

ETIQUETA_ESPECIES = "Especies que acepta"
ETIQUETA_TAMANO = "Tamaño máximo"
ETIQUETA_DURACION = "Duración máxima"
ETIQUETA_DISPONIBILIDAD = "Disponibilidad"
ETIQUETA_REANUDACION = "Fecha de reanudación"
ETIQUETA_CUPO = "Cupo"

MENSAJE_ESPECIE_INVALIDA = "Elegí una especie de la lista."
MENSAJE_TAMANO_INVALIDO = "Elegí un tamaño de la lista."
MENSAJE_DURACION_LARGA = f"La duración máxima no puede superar los {MAX_DURACION_MAXIMA_DIAS} días."
MENSAJE_PAUSA_PASADA = "La fecha de reanudación tiene que ser posterior a hoy."
MENSAJE_CUPO = f"El cupo tiene que estar entre 1 y {MAX_CUPO_DECLARADO}."
MENSAJE_CUPO_EXCEDE = "Podría exceder la capacidad de su vivienda"
MENSAJE_ANIMALES_A_CARGO = (
    "No se puede desactivar el perfil porque tenés animales a cargo. Podés pausarlo."
)


class PerfilTransitoInvalido(ValueError):
    """Algún dato del perfil no es válido. "errores" va de campo a mensaje."""

    def __init__(self, errores):
        super().__init__("; ".join(errores.values()))
        self.errores = errores


class PerfilTransitoIncompleto(ValueError):
    """Faltan campos obligatorios (CU-06, 7A). "faltantes" los nombra en palabras."""

    def __init__(self, faltantes):
        super().__init__("Faltan datos: " + ", ".join(faltantes))
        self.faltantes = faltantes


class HogarIncompleto(PerfilTransitoIncompleto):
    """Faltan datos del hogar (CU-06, 2A): hay que pedirlos y volver al perfil."""


class SinPerfilActivo(ValueError):
    """La persona no tiene un perfil de tránsito activo que desactivar."""


class DesactivacionNoPermitida(ValueError):
    """No se puede desactivar el perfil porque hay animales a cargo."""


class CupoSuperaEstimado(ValueError):
    """El cupo declarado supera el estimado.

    Es solo una sugerencia: la persona puede confirmar el cupo igual. "estimado" trae el
    número sugerido.
    """

    def __init__(self, estimado):
        super().__init__(MENSAJE_CUPO_EXCEDE)
        self.estimado = estimado


def mensaje_duracion_minima():
    return f"La duración mínima es de {config.DURACION_MINIMA_TRANSITO_DIAS} días"


def cupo_estimado(domicilio):
    """Cupo que el sistema sugiere para una vivienda.

    Una casa suma 3, un departamento u otra vivienda suma 1, y un patio suma 2, con un
    máximo de 5. Los convivientes, los niños y las mascotas propias no cambian el
    resultado. Devuelve None si todavía faltan datos de la vivienda.
    """
    if domicilio is None or not domicilio.tipo_vivienda or domicilio.tiene_patio is None:
        return None
    base = CUPO_POR_VIVIENDA.get(domicilio.tipo_vivienda)
    if base is None:
        return None
    extra = CUPO_EXTRA_POR_PATIO if domicilio.tiene_patio else 0
    return min(base + extra, MAX_CUPO_ESTIMADO)


def _etiqueta_hogar(campo):
    texto = str(Domicilio._meta.get_field(campo).verbose_name)
    return texto[:1].upper() + texto[1:]


def datos_faltantes_hogar(usuario):
    """Lo que falta del domicilio y del hogar, en palabras."""
    domicilio = Domicilio.objects.filter(usuario=usuario).first()
    if domicilio is None:
        return ["Domicilio", *(_etiqueta_hogar(campo) for campo in CAMPOS_HOGAR)]
    return [_etiqueta_hogar(campo) for campo in domicilio.hogar_faltante()]


def _campos_faltantes(especies, tamano_maximo, duracion, disponibilidad, pausa_hasta, cupo):
    faltantes = []
    if not especies:
        faltantes.append(ETIQUETA_ESPECIES)
    if not tamano_maximo:
        faltantes.append(ETIQUETA_TAMANO)
    if duracion is None:
        faltantes.append(ETIQUETA_DURACION)
    if disponibilidad is None:
        faltantes.append(ETIQUETA_DISPONIBILIDAD)
    elif not disponibilidad and pausa_hasta is None:
        faltantes.append(ETIQUETA_REANUDACION)
    if cupo is None:
        faltantes.append(ETIQUETA_CUPO)
    return faltantes


def _errores(especies, tamano_maximo, duracion, disponibilidad, pausa_hasta, cupo):
    errores = {}
    if not set(especies) <= {valor for valor, _ in FichaAnimal.Especie.choices}:
        errores["especies"] = MENSAJE_ESPECIE_INVALIDA
    if tamano_maximo not in dict(FichaAnimal.Tamano.choices):
        errores["tamano_maximo"] = MENSAJE_TAMANO_INVALIDO
    if duracion < config.DURACION_MINIMA_TRANSITO_DIAS:
        errores["duracion_maxima_dias"] = mensaje_duracion_minima()
    elif duracion > MAX_DURACION_MAXIMA_DIAS:
        errores["duracion_maxima_dias"] = MENSAJE_DURACION_LARGA
    if not disponibilidad and pausa_hasta <= timezone.localdate():
        errores["pausa_hasta"] = MENSAJE_PAUSA_PASADA
    if not 1 <= cupo <= MAX_CUPO_DECLARADO:
        errores["cupo_declarado"] = MENSAJE_CUPO
    return errores


def guardar_perfil_transito(
    usuario,
    *,
    especies,
    tamano_maximo,
    duracion_maxima_dias,
    disponibilidad,
    pausa_hasta=None,
    cupo_declarado,
    acepta_medicacion=False,
    acepta_conducta=False,
    confirmar_exceso=False,
):
    """Guarda y activa el perfil de hogar de tránsito.

    No guarda nada si faltan datos del hogar (HogarIncompleto), si faltan campos
    obligatorios (PerfilTransitoIncompleto) o si algún valor no es válido
    (PerfilTransitoInvalido). Si ya había un perfil, lo actualiza y lo
    deja activo. El rol de hogar de tránsito sale de tener el perfil activo.
    Si el cupo supera el estimado de la vivienda lanza CupoSuperaEstimado, salvo que
    se pase confirmar_exceso=True.
    """
    especies = list(especies or [])

    faltantes_hogar = datos_faltantes_hogar(usuario)
    if faltantes_hogar:
        raise HogarIncompleto(faltantes_hogar)

    faltantes = _campos_faltantes(
        especies, tamano_maximo, duracion_maxima_dias, disponibilidad, pausa_hasta, cupo_declarado
    )
    if faltantes:
        raise PerfilTransitoIncompleto(faltantes)

    errores = _errores(
        especies, tamano_maximo, duracion_maxima_dias, disponibilidad, pausa_hasta, cupo_declarado
    )
    if errores:
        raise PerfilTransitoInvalido(errores)

    # El estimado es solo una sugerencia: se avisa y la persona puede confirmar.
    estimado = cupo_estimado(Domicilio.objects.filter(usuario=usuario).first())
    if not confirmar_exceso and estimado is not None and cupo_declarado > estimado:
        raise CupoSuperaEstimado(estimado)

    perfil, _ = PerfilTransito.objects.update_or_create(
        usuario=usuario,
        defaults={
            # Se guardan en el orden de la ficha de animal y sin repetidos.
            "especies_aceptadas": ",".join(
                valor for valor, _ in FichaAnimal.Especie.choices if valor in especies
            ),
            "tamano_maximo": tamano_maximo,
            "duracion_maxima_dias": duracion_maxima_dias,
            "acepta_medicacion": acepta_medicacion,
            "acepta_conducta": acepta_conducta,
            "disponibilidad": disponibilidad,
            "pausa_hasta": None if disponibilidad else pausa_hasta,
            "cupo_declarado": cupo_declarado,
            "activo": True,
        },
    )
    return perfil


def es_hogar_de_transito(usuario):
    """True si la persona tiene un perfil de tránsito activo.

    El rol de hogar de tránsito se deriva de eso: no se guarda en "Usuario.rol".
    """
    if not usuario.is_authenticated:
        return False
    return PerfilTransito.objects.filter(usuario=usuario, activo=True).exists()


def esta_disponible(perfil, hoy=None):
    """True si el hogar puede recibir animales hoy.

    En pausa deja de estarlo hasta la fecha de reanudación; al llegar esa fecha vuelve a
    estar disponible solo, sin tareas programadas.
    """
    if not perfil.activo:
        return False
    if perfil.disponibilidad:
        return True
    hoy = hoy or timezone.localdate()
    return perfil.pausa_hasta is not None and perfil.pausa_hasta <= hoy


def animales_alojados(usuario):
    """Cuántos animales tiene alojados el hogar hoy.

    Provisorio: los alojamientos todavía no existen, así que por ahora
    es siempre 0. Cuando los tengamos, esta es la única función a conectar: de ella salen
    tiene_animales_a_cargo y cupo_libre.
    """
    return 0


def tiene_animales_a_cargo(usuario):
    """True si el hogar tiene animales alojados hoy."""
    return animales_alojados(usuario) > 0


def cupo_libre(perfil):
    """Plazas que le quedan al hogar: el cupo declarado menos los animales alojados."""
    return max(perfil.cupo_declarado - animales_alojados(perfil.usuario), 0)


def desactivar_perfil_transito(usuario):
    """Desactiva el perfil de tránsito.

    No se puede con animales a cargo: lanza DesactivacionNoPermitida y el perfil sigue
    activo (la persona puede pausarlo). Los datos del perfil se conservan y guardarlo de
    nuevo lo reactiva.
    """
    perfil = PerfilTransito.objects.filter(usuario=usuario, activo=True).first()
    if perfil is None:
        raise SinPerfilActivo("No hay un perfil de tránsito activo.")
    if tiene_animales_a_cargo(usuario):
        raise DesactivacionNoPermitida(MENSAJE_ANIMALES_A_CARGO)
    perfil.activo = False
    perfil.save(update_fields=["activo"])
    return perfil


def hogar_habilitado(perfil, hoy=None):
    """True si el hogar puede recibir un animal hoy.

    Pide el perfil activo y disponible (no en pausa), la cuenta activa y sin sanción
    vigente, y al menos una plaza libre.
    """
    usuario = perfil.usuario
    return (
        esta_disponible(perfil, hoy)
        and usuario.estado_cuenta == EstadoCuenta.ACTIVA
        and not esta_suspendido(usuario)
        and cupo_libre(perfil) > 0
    )
