from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.core.datos_prueba.personas import PERSONAS
from apps.cuentas import geo
from apps.cuentas.models import Domicilio, EstadoCuenta, Rol, Sancion
from apps.cuentas.servicios import puede_postularse_a_adoptar, sancion_vigente
from apps.fichas.models import FichaAnimal
from apps.fichas.servicios import crear_ficha
from apps.imagenes.models import Fotografia
from apps.publicaciones.models import Publicacion
from apps.transito.models import PerfilTransito
from apps.transito.servicios import hogar_habilitado

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

    assert not get_user_model().objects.filter(email="persona@example.com").exists()
    assert get_user_model().objects.filter(pk=datos_viejos["admin"].pk).exists()
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


def usuario(clave):
    return get_user_model().objects.get(email=PERSONAS[clave].email)


def test_crea_una_cuenta_por_persona_con_correos_que_no_reciben_correo():
    cargar()

    correos = set(get_user_model().objects.values_list("email", flat=True))
    assert correos == {persona.email for persona in PERSONAS.values()}
    assert all(correo.endswith("@example.com") for correo in correos)


def test_los_domicilios_quedan_en_ushuaia_aunque_se_desplacen():
    cargar()

    for domicilio in Domicilio.objects.all():
        punto = domicilio.ubicacion_desplazada
        assert geo.en_zona(punto.x, punto.y), domicilio.usuario.email


def test_hay_cuentas_en_cada_estado():
    cargar()

    assert usuario("gabriela").rol == Rol.MODERADOR
    assert usuario("bruno").estado_cuenta == EstadoCuenta.PENDIENTE
    assert not Domicilio.objects.filter(usuario=usuario("bruno")).exists()
    assert sancion_vigente(usuario("valeria")).tipo == Sancion.Tipo.TEMPORAL
    assert sancion_vigente(usuario("marcos")).tipo == Sancion.Tipo.PERMANENTE


def test_los_hogares_de_transito_quedan_en_situaciones_distintas():
    cargar()

    habilitados = {
        perfil.usuario.email for perfil in PerfilTransito.objects.all() if hogar_habilitado(perfil)
    }
    assert usuario("lucia").email in habilitados
    assert usuario("tomas").email not in habilitados  # en pausa
    assert usuario("valeria").email not in habilitados  # suspendida


def test_quienes_cuentan_su_experiencia_pueden_postularse_para_adoptar():
    cargar()

    for clave in ("ana", "carla", "federico", "paula", "romina"):
        assert puede_postularse_a_adoptar(usuario(clave)), clave


def test_se_puede_correr_dos_veces_sin_duplicar():
    cargar()
    cargar()

    assert get_user_model().objects.count() == len(PERSONAS)
    assert Sancion.objects.count() == 2
