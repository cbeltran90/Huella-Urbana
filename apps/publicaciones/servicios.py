from django.db import transaction

from apps.fichas.servicios import crear_ficha, crear_ficha_sin_responsable
from apps.imagenes.servicios import registrar_fotografia

from . import ubicacion
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
