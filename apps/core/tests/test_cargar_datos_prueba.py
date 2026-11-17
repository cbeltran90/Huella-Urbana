from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.cuentas.models import Domicilio, EstadoCuenta
from apps.fichas.models import FichaAnimal
from apps.fichas.servicios import crear_ficha
from apps.imagenes.models import Fotografia
from apps.publicaciones.models import Publicacion

pytestmark = pytest.mark.django_db

PUNTO = Point(-68.31129, -54.80670, srid=4326)


def cargar(**opciones):
    salida = StringIO()
    call_command("cargar_datos_prueba", password="clave-de-prueba", stdout=salida, **opciones)
    return salida.getvalue()


@pytest.fixture
def datos_viejos(settings, tmp_path):
    """Un superusuario y una persona con una ficha, una publicación y una foto."""
    settings.MEDIA_ROOT = tmp_path
    modelo = get_user_model()
    admin = modelo.objects.create_superuser("admin@example.com", "admin", "clave")
    Domicilio.objects.create(usuario=admin, ubicacion=PUNTO, ubicacion_desplazada=PUNTO)
    persona = modelo.objects.create_user(
        "persona@example.com", "persona", "clave", estado_cuenta=EstadoCuenta.ACTIVA
    )
    ficha = crear_ficha(persona, {"nombre": "Viejo", "especie": "perro"})
    Publicacion.objects.create(
        tipo=Publicacion.Tipo.EXTRAVIO, autor=persona, ficha=ficha, ubicacion=PUNTO
    )
    ruta = default_storage.save("fotos/vieja.jpg", ContentFile(b"foto"))
    Fotografia.objects.create(archivo=ruta, hash_sha256="0" * 64, ficha=ficha)
    return {"admin": admin, "ruta": ruta}


def test_la_contrasena_es_obligatoria():
    with pytest.raises(CommandError, match="--password"):
        call_command("cargar_datos_prueba", stdout=StringIO())


def test_vaciar_borra_todo_menos_los_superusuarios(datos_viejos):
    cargar(vaciar=True, sin_preguntar=True)

    assert list(get_user_model().objects.all()) == [datos_viejos["admin"]]
    assert Domicilio.objects.filter(usuario=datos_viejos["admin"]).exists()
    assert not FichaAnimal.objects.filter(nombre="Viejo").exists()
    assert not Publicacion.objects.exists()
    assert not Fotografia.objects.exists()


def test_vaciar_borra_los_archivos_de_las_fotos(datos_viejos, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        cargar(vaciar=True, sin_preguntar=True)

    assert not default_storage.exists(datos_viejos["ruta"])


def test_sin_escribir_la_confirmacion_no_borra_nada(datos_viejos, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda mensaje: "si")

    with pytest.raises(CommandError, match="No se borró nada"):
        cargar(vaciar=True)

    assert get_user_model().objects.filter(email="persona@example.com").exists()
    assert default_storage.exists(datos_viejos["ruta"])


def test_con_la_confirmacion_vacia_la_base(datos_viejos, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda mensaje: "vaciar")

    salida = cargar(vaciar=True)

    assert "Base vaciada" in salida
    assert not get_user_model().objects.filter(email="persona@example.com").exists()
