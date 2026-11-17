"""Vacía la base para cargar los datos de prueba desde cero.

Quedan los superusuarios (con su domicilio y sus perfiles) y la configuración del sitio. Se
borra todo lo demás: cuentas, fichas, publicaciones, fotos (también los archivos),
postulaciones, alojamientos, adopciones, sanciones y avisos.
"""

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db import transaction

from apps.adopcion.models import Adopcion
from apps.cuentas.models import Sancion
from apps.fichas.models import Coincidencia, FichaAnimal
from apps.imagenes.models import Fotografia
from apps.notificaciones.models import Notificacion
from apps.publicaciones.models import Publicacion
from apps.transito.models import Alojamiento, Postulacion

# En este orden: las adopciones y los alojamientos protegen a la ficha y al hogar (PROTECT).
MODELOS = {
    "adopciones": Adopcion,
    "alojamientos": Alojamiento,
    "postulaciones": Postulacion,
    "coincidencias": Coincidencia,
    "avisos": Notificacion,
    "fotos": Fotografia,
    "publicaciones": Publicacion,
    "fichas": FichaAnimal,
    "sanciones": Sancion,
}


@transaction.atomic
def vaciar_base():
    """Borra los datos y devuelve cuántos se borraron de cada cosa."""
    archivos = list(Fotografia.objects.values_list("archivo", flat=True))
    borrados = {}
    for nombre, modelo in MODELOS.items():
        borrados[nombre] = modelo.objects.count()
        modelo.objects.all().delete()
    # Con las cuentas se borran sus domicilios y perfiles (CASCADE).
    cuentas = get_user_model().objects.filter(is_superuser=False)
    borrados["cuentas"] = cuentas.count()
    cuentas.delete()
    # Los archivos se borran solo si la transacción se confirma: si algo falla, quedan.
    transaction.on_commit(lambda: _borrar_archivos(archivos))
    return borrados


def _borrar_archivos(rutas):
    for ruta in rutas:
        default_storage.delete(ruta)
