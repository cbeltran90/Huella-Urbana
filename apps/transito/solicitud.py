"""Solicitar tránsito para un animal encontrado"""

from django.contrib.gis.geos import Point
from django.db import transaction

from apps.cuentas import geo
from apps.fichas.models import FichaAnimal
from apps.fichas.permisos import es_cuidador, es_moderador
from apps.fichas.servicios import cambiar_estado
from apps.publicaciones import servicios as publicaciones
from apps.publicaciones import ubicacion

# Largo de FichaAnimal.cuidador_contacto.
CONTACTO_MAXIMO = 100

MENSAJE_NO_PUEDE = "No podés solicitar tránsito para este animal."
MENSAJE_CONTACTO_LARGO = f"El contacto no puede superar los {CONTACTO_MAXIMO} caracteres."
MENSAJE_FALTA_PUNTO = "Marcá en el mapa dónde está el animal."
MENSAJE_FUERA_DE_ZONA = "El punto tiene que estar en Ushuaia y alrededores."


class SolicitudNoPermitida(Exception):
    """Quien lo pide no puede, o la ficha no está en "sin responsable"."""


class ContactoInvalido(ValueError):
    """El contacto que cargó el moderador no es válido."""


class UbicacionInvalida(ValueError):
    """Falta el punto del animal o está fuera de la zona. El mensaje se puede mostrar."""


def puede_solicitar(usuario, ficha):
    """Quien tiene al animal a su cargo o un moderador, con la ficha en "sin responsable".

    Si el animal no está a cargo de un usuario, solo lo puede pedir un moderador (extensión 1A);
    eso sale solo de la regla: sin cuidador, nadie más cumple.
    """
    if ficha.estado != FichaAnimal.Estado.SIN_RESPONSABLE:
        return False
    return es_cuidador(usuario, ficha) or es_moderador(usuario)


def necesita_punto(ficha):
    """True si hay que marcar el punto en el mapa para publicar la ficha.

    Pasa cuando no la tiene a cargo un usuario (lo marca un moderador) o cuando quien la tiene
    no tiene domicilio: en los demás casos se usa el punto aproximado de su domicilio.
    """
    cuidador = ficha.cuidador
    return cuidador is None or ubicacion.punto_de_domicilio(cuidador) is None


def _punto_en_zona(punto):
    if not isinstance(punto, Point) or punto.empty:
        raise UbicacionInvalida(MENSAJE_FALTA_PUNTO)
    if not geo.en_zona(punto.x, punto.y):
        raise UbicacionInvalida(MENSAJE_FUERA_DE_ZONA)
    return punto


@transaction.atomic
def solicitar_transito(ficha, actor, *, contacto="", punto=None):
    """Pasa la ficha a "en adopción", la hace pública y la publica.

    - 'contacto' solo se guarda si lo carga un moderador y la ficha no está a cargo de un
      usuario.
    - 'punto' (longitud, latitud en 4326) solo hace falta si 'necesita_punto(ficha)'; si no, se
      ignora y se usa el domicilio de quien la tiene a cargo.
    Todo ocurre en una transacción: si algo falla, la ficha queda como estaba. Después de
    guardar, el módulo de publicaciones avisa a los hogares compatibles.
    Lanza 'SolicitudNoPermitida', 'ContactoInvalido' o 'UbicacionInvalida'.
    """
    # Se bloquea la ficha y se relee: si otra persona la cambió mientras tanto, se valida
    # contra lo que hay en la base y no contra lo que tenía este objeto.
    FichaAnimal.objects.select_for_update().get(pk=ficha.pk)
    ficha.refresh_from_db(fields=["estado", "cuidador"])

    if not puede_solicitar(actor, ficha):
        raise SolicitudNoPermitida(MENSAJE_NO_PUEDE)

    cambios = {"es_privada": False}
    contacto = (contacto or "").strip()
    if contacto and ficha.cuidador_id is None and es_moderador(actor):
        if len(contacto) > CONTACTO_MAXIMO:
            raise ContactoInvalido(MENSAJE_CONTACTO_LARGO)
        cambios["cuidador_contacto"] = contacto

    punto = _punto_en_zona(punto) if necesita_punto(ficha) else None

    cambiar_estado(ficha, FichaAnimal.Estado.EN_ADOPCION, actor=actor, cambios=cambios)
    publicaciones.publicar_adopcion_de_ficha(ficha, actor, punto=punto)
    return ficha
