"""Avisos que dispara una publicación nueva."""

import logging

logger = logging.getLogger(__name__)

TIPO_AVISO = "coincidencia_transito"


def avisar_hogares_compatibles(publicacion):
    """Notifica a los hogares compatibles con la ficha de la publicación. Devuelve cuántos."""
    # Se importan acá y no arriba para evitar ciclos entre las apps.
    from apps.notificaciones.servicios import notificar
    from apps.transito.servicios import hogares_compatibles

    ficha = publicacion.ficha
    try:
        hogares = list(hogares_compatibles(ficha))
    except Exception:
        logger.exception("No se pudieron buscar los hogares compatibles")
        return 0

    avisados = 0
    especie = ficha.get_especie_display().lower()
    for hogar in hogares:
        usuario = getattr(hogar, "usuario", hogar)
        if usuario == publicacion.autor:
            continue
        try:
            notificar(
                usuario,
                TIPO_AVISO,
                "Una mascota necesita un hogar",
                f"Hay un {especie} en adopción que encaja con tu hogar.",
                ficha=ficha,
                publicacion=publicacion,
            )
        except Exception:
            logger.exception("No se pudo avisar a un hogar compatible")
        else:
            avisados += 1
    return avisados
