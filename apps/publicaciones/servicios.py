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
    Devuelve (ubicacion, ubicacion_desplazada).
    """
    cuidador = ficha.cuidador
    if cuidador is not None:
        lugar = ubicacion.punto_de_domicilio(cuidador)
        if lugar is not None:
            return lugar, None
    if punto is None:
        if cuidador is None:
            raise ValueError("Falta la ubicación: el animal no está a cargo de un usuario.")
        raise ValueError("Falta la ubicación: quien lo tiene a cargo no tiene domicilio.")
    if cuidador is not None and actor == cuidador:
        return ubicacion.registrar_domicilio(cuidador, punto), None
    desplazado = ubicacion.desplazar_punto(punto)
    return desplazado, desplazado


@transaction.atomic
def _crear_publicacion_de_adopcion(ficha, actor, *, punto, descripcion, telefono_visible):
    lugar, desplazada = _punto_para_publicar(ficha, punto, actor)
    # Una sola publicación vigente de adopción o tránsito por ficha (ahora vuelve a adopción).
    ficha.publicaciones.filter(
        estado=Publicacion.Estado.VIGENTE,
        tipo__in=[Publicacion.Tipo.ADOPCION, Publicacion.Tipo.TRANSITO],
    ).update(estado=Publicacion.Estado.RESUELTA)
    # El hallazgo ya cumplió: se cierra y sigue vinculado a la ficha, como parte de su historia.
    # Su ubicación exacta queda solo en él: no se copia a la publicación de adopción.
    ficha.publicaciones.filter(
        estado=Publicacion.Estado.VIGENTE, tipo=Publicacion.Tipo.HALLAZGO
    ).update(estado=Publicacion.Estado.RESUELTA)

    return Publicacion.objects.create(
        tipo=Publicacion.Tipo.ADOPCION,
        autor=ficha.cuidador or actor,
        ficha=ficha,
        ubicacion=lugar,
        ubicacion_desplazada=desplazada,
        descripcion=descripcion,
        telefono_visible=telefono_visible,
        especie=ficha.especie,
        tamano=ficha.tamano,
        raza=ficha.raza,
        color=ficha.color,
    )


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
    publicacion = _crear_publicacion_de_adopcion(
        ficha,
        actor,
        punto=punto,
        descripcion=descripcion,
        telefono_visible=telefono_visible,
    )
    try:
        avisos.avisar_hogares_compatibles(publicacion)
    except Exception:
        logger.exception("No se pudo avisar a los hogares compatibles")
    return publicacion
