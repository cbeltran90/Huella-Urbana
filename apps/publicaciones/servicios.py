import logging

from django.db import transaction

from apps.fichas.models import FichaAnimal
from apps.fichas.servicios import (
    crear_ficha,
    crear_ficha_en_adopcion,
    crear_ficha_sin_responsable,
)
from apps.imagenes.servicios import registrar_fotografia

from . import avisos, ubicacion
from .models import Publicacion

logger = logging.getLogger(__name__)


@transaction.atomic
def publicar_extravio(
    usuario,
    *,
    ficha=None,
    animal=None,
    estado_aparente="",
    descripcion="",
    archivo=None,
    punto=None,
):
    """Publica el extravío de una ficha propia o de un animal nuevo.

    - "ficha": ficha de la que el usuario es responsable; si es None se crea una con "animal"
      (diccionario con los datos de la ficha). Una ficha nueva exige foto.
    - "punto": ubicación indicada por el usuario; solo se usa si no tiene domicilio.
    Lanza "ImagenInvalida" si la foto no sirve; no queda nada a medias (transacción).
    """
    if ficha is None:
        if archivo is None:
            raise ValueError("Una ficha nueva necesita una foto.")
        ficha = crear_ficha(usuario, animal or {})

    lugar = ubicacion.punto_de_domicilio(usuario)
    if lugar is None:
        if punto is None:
            raise ValueError("Falta la ubicación: el usuario no tiene domicilio.")
        lugar = ubicacion.registrar_domicilio(usuario, punto)

    if archivo is not None:
        registrar_fotografia(archivo=archivo, autor=usuario, ficha=ficha)

    return Publicacion.objects.create(
        tipo=Publicacion.Tipo.EXTRAVIO,
        autor=usuario,
        ficha=ficha,
        ubicacion=lugar,
        domicilio=ubicacion.domicilio_de(usuario),
        descripcion=descripcion,
        estado_aparente=estado_aparente,
        especie=ficha.especie,
        tamano=ficha.tamano,
        raza=ficha.raza,
        color=ficha.color,
    )


@transaction.atomic
def publicar_hallazgo(
    usuario,
    *,
    animal,
    archivo,
    punto,
    estado_aparente="",
    descripcion="",
    tiene_consigo=False,
):
    """Publica el hallazgo de un animal con una ficha nueva en "sin responsable".

    - 'punto': la ubicación EXACTA donde se encontró (a diferencia del extravío, no se desplaza).
    - 'tiene_consigo': si es True el animal queda a cargo del usuario; si no, de nadie.
    Después la vista ofrece las fichas candidatas (comparación) y deja vincular una
    (apps/publicaciones/vinculacion.py).
    Lanza 'ImagenInvalida' si la foto no sirve; no queda nada a medias (transacción).
    """
    ficha = crear_ficha_sin_responsable(animal, cuidador=usuario if tiene_consigo else None)
    registrar_fotografia(archivo=archivo, autor=usuario, ficha=ficha)
    return Publicacion.objects.create(
        tipo=Publicacion.Tipo.HALLAZGO,
        autor=usuario,
        ficha=ficha,
        ubicacion=punto,
        descripcion=descripcion,
        estado_aparente=estado_aparente,
        especie=ficha.especie,
        tamano=ficha.tamano,
        raza=ficha.raza,
        color=ficha.color,
    )


@transaction.atomic
def _crear_alta_en_adopcion(usuario, *, animal, archivos, descripcion, telefono_visible, punto):
    lugar = ubicacion.punto_de_domicilio(usuario)
    if lugar is None:
        if punto is None:
            raise ValueError("Falta la ubicación: el usuario no tiene domicilio.")
        lugar = ubicacion.registrar_domicilio(usuario, punto)

    ficha = crear_ficha_en_adopcion(animal, cuidador=usuario)
    for archivo in archivos:
        registrar_fotografia(archivo=archivo, autor=usuario, ficha=ficha)

    return Publicacion.objects.create(
        tipo=Publicacion.Tipo.ADOPCION,
        autor=usuario,
        ficha=ficha,
        ubicacion=lugar,
        domicilio=ubicacion.domicilio_de(usuario),
        descripcion=descripcion,
        telefono_visible=telefono_visible,
        especie=ficha.especie,
        tamano=ficha.tamano,
        raza=ficha.raza,
        color=ficha.color,
    )


def alta_en_adopcion(usuario, *, animal, archivos, punto=None, descripcion="", telefono_visible=""):
    """Alta directa en adopción: ficha nueva en "en adopción" a cargo del usuario y su publicación.

    - 'archivos': las fotos (al menos una), todas de la ficha.
    - 'punto': ubicación indicada por el usuario; solo se usa si no tiene domicilio.
    La publicación sale con la ubicación desplazada del domicilio. Después de guardar todo, se
    avisa a los hogares compatibles; si eso falla, el alta queda igual.
    Lanza 'ImagenInvalida' si una foto no sirve; no queda nada a medias (transacción).
    """
    if not archivos:
        raise ValueError("Hace falta al menos una foto.")
    publicacion = _crear_alta_en_adopcion(
        usuario,
        animal=animal,
        archivos=archivos,
        descripcion=descripcion,
        telefono_visible=telefono_visible,
        punto=punto,
    )
    avisos.avisar_hogares_compatibles(publicacion)
    return publicacion


def _punto_para_publicar(ficha, punto, actor):
    """El punto que se muestra en la publicación de adopción de una ficha ya existente.

    - A cargo de un usuario con domicilio: su punto desplazado.
    - A cargo de un usuario sin domicilio, y es él quien publica: "punto", que se registra como
      su domicilio.
    - Lo carga un moderador (sin usuario a cargo, o a cargo de alguien sin domicilio que no es
      quien publica): "punto" se desplaza acá, nunca sale tal cual, y no se guarda como
      domicilio de nadie. Va también a "ubicacion_desplazada".
    Devuelve (ubicacion, ubicacion_desplazada, domicilio): el domicilio es de donde salió
    el punto, o None si lo marcó un moderador.
    """
    cuidador = ficha.cuidador
    if cuidador is not None:
        lugar = ubicacion.punto_de_domicilio(cuidador)
        if lugar is not None:
            return lugar, None, ubicacion.domicilio_de(cuidador)
    if punto is None:
        if cuidador is None:
            raise ValueError("Falta la ubicación: la mascota no está a cargo de un usuario.")
        raise ValueError("Falta la ubicación: quien lo tiene a cargo no tiene domicilio.")
    if cuidador is not None and actor == cuidador:
        lugar = ubicacion.registrar_domicilio(cuidador, punto)
        return lugar, None, ubicacion.domicilio_de(cuidador)
    desplazado = ubicacion.desplazar_punto(punto)
    return desplazado, desplazado, None


@transaction.atomic
def _crear_publicacion_de_estado(ficha, actor, *, tipo, punto, descripcion, telefono_visible):
    """La publicación de adopción o de tránsito de una ficha que ya existe."""
    lugar, desplazada, domicilio = _punto_para_publicar(ficha, punto, actor)
    # Una sola publicación vigente de adopción o tránsito por ficha (2.8).
    resolver_publicaciones_de_estado(ficha)
    # El hallazgo ya cumplió: se cierra y sigue vinculado a la ficha, como parte de su historia.
    # Su ubicación exacta queda solo en él: no se copia a la publicación nueva.
    ficha.publicaciones.filter(
        estado=Publicacion.Estado.VIGENTE, tipo=Publicacion.Tipo.HALLAZGO
    ).update(estado=Publicacion.Estado.RESUELTA)

    return Publicacion.objects.create(
        tipo=tipo,
        autor=ficha.cuidador or actor,
        ficha=ficha,
        ubicacion=lugar,
        ubicacion_desplazada=desplazada,
        domicilio=domicilio,
        descripcion=descripcion,
        telefono_visible=telefono_visible,
        especie=ficha.especie,
        tamano=ficha.tamano,
        raza=ficha.raza,
        color=ficha.color,
    )


def resolver_publicaciones_de_estado(ficha):
    """La publicación vigente de adopción o de tránsito de la ficha pasa a resuelta (2.8).

    Lo usa "cambiar_estado" cuando la ficha deja de estar en adopción o en tránsito. La
    publicación del estado nuevo la genera quien lo provoca, porque necesita datos que
    el cambio de estado no tiene. Devuelve cuántas resolvió.
    """
    return ficha.publicaciones.filter(
        estado=Publicacion.Estado.VIGENTE,
        tipo__in=[Publicacion.Tipo.ADOPCION, Publicacion.Tipo.TRANSITO],
    ).update(estado=Publicacion.Estado.RESUELTA)


def publicar_adopcion_de_ficha(ficha, actor, *, punto=None, descripcion="", telefono_visible=""):
    """Publica en adopción una ficha que ya existe.

    No cambia el estado de la ficha: antes tiene que estar en "en adopción" (lo hace
    "cambiar_estado") o lanza ValueError. Quien llama puede hacer las dos cosas en una misma
    transacción.
    - 'actor': quien publica; es el autor si el animal no está a cargo de un usuario.
    - 'punto': solo hace falta si no hay un domicilio de quien lo tiene a cargo, o si no lo
      tiene a cargo un usuario (lo carga un moderador). Si lo marca un moderador, se desplaza
      acá y no se guarda como domicilio de nadie; solo se registra como domicilio si quien
      publica es el propio cuidador.
    La publicación sale con una ubicación aproximada, nunca la exacta. Cierra el hallazgo
    vigente de la ficha (sigue vinculado) y la publicación de adopción o tránsito anterior.
    Después de guardar, avisa a los hogares compatibles; si el aviso falla, la publicación queda.
    """
    if ficha.estado != FichaAnimal.Estado.EN_ADOPCION:
        raise ValueError("La ficha tiene que estar en adopción para publicarla.")
    publicacion = _crear_publicacion_de_estado(
        ficha,
        actor,
        tipo=Publicacion.Tipo.ADOPCION,
        punto=punto,
        descripcion=descripcion,
        telefono_visible=telefono_visible,
    )
    try:
        avisos.avisar_hogares_compatibles(publicacion)
    except Exception:
        logger.exception("No se pudo avisar a los hogares compatibles")
    return publicacion


def publicar_transito_de_ficha(ficha, actor):
    """Publica en tránsito una ficha que acaba de pasar a "en tránsito".

    El estado lo cambia antes "cambiar_estado", que resolvió la publicación de adopción. La ficha
    tiene que tener a su hogar como cuidador. La ubicación es el punto
    desplazado del domicilio del hogar; la descripción y el teléfono se toman de la publicación
    de adopción anterior.
    """
    if ficha.estado != FichaAnimal.Estado.EN_TRANSITO:
        raise ValueError("La ficha tiene que estar en tránsito para publicarla.")
    if ficha.cuidador is None:
        raise ValueError("Falta el hogar de tránsito: la ficha no tiene cuidador.")
    anterior = ficha.publicaciones.filter(tipo=Publicacion.Tipo.ADOPCION).order_by("-pk").first()
    return _crear_publicacion_de_estado(
        ficha,
        actor,
        tipo=Publicacion.Tipo.TRANSITO,
        punto=None,
        descripcion=anterior.descripcion if anterior else "",
        telefono_visible=anterior.telefono_visible if anterior else "",
    )
