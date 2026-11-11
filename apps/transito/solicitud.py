"""Solicitar tránsito para un animal encontrado."""

from django.db import transaction

from apps.fichas.models import FichaAnimal
from apps.fichas.permisos import es_cuidador, es_moderador
from apps.fichas.servicios import cambiar_estado

# Largo de FichaAnimal.cuidador_contacto.
CONTACTO_MAXIMO = 100

MENSAJE_NO_PUEDE = "No podés solicitar tránsito para este animal."
MENSAJE_CONTACTO_LARGO = f"El contacto no puede superar los {CONTACTO_MAXIMO} caracteres."


class SolicitudNoPermitida(Exception):
    """Quien lo pide no puede, o la ficha no está en "sin responsable"."""


class ContactoInvalido(ValueError):
    """El contacto que cargó el moderador no es válido."""


def puede_solicitar(usuario, ficha):
    """Quien tiene al animal a su cargo o un moderador, con la ficha en "sin responsable".

    Si el animal no está a cargo de un usuario, solo lo puede pedir un moderador;
    eso sale solo de la regla: sin cuidador, nadie más cumple.
    """
    if ficha.estado != FichaAnimal.Estado.SIN_RESPONSABLE:
        return False
    return es_cuidador(usuario, ficha) or es_moderador(usuario)


@transaction.atomic
def solicitar_transito(ficha, actor, *, contacto=""):
    """Pasa la ficha a "en adopción" y la hace pública.

    'contacto' solo se guarda si lo carga un moderador y la ficha no está a cargo de un usuario
    . La publicación y el aviso a los hogares los agrega el módulo de
    publicaciones (todavía no).
    Lanza 'SolicitudNoPermitida' o 'ContactoInvalido'.
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

    cambiar_estado(ficha, FichaAnimal.Estado.EN_ADOPCION, actor=actor, cambios=cambios)
    return ficha
