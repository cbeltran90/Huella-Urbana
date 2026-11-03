from django.db import transaction

from apps.fichas.servicios import crear_ficha
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
