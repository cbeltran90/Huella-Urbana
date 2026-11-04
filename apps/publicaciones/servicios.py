from django.db import transaction

from apps.fichas.servicios import (
    crear_ficha,
    crear_ficha_en_adopcion,
    crear_ficha_sin_responsable,
)
from apps.imagenes.servicios import registrar_fotografia

from . import avisos, ubicacion
from .models import Publicacion


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
    La comparación con fichas existentes y el vínculo a una candidata llegan.
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
