from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.adopcion.models import Adopcion
from apps.core.datos_prueba.mascotas import FOTOS
from apps.core.datos_prueba.personas import PERSONAS
from apps.cuentas import geo
from apps.cuentas.models import Domicilio, EstadoCuenta, Rol, Sancion
from apps.cuentas.servicios import puede_postularse_a_adoptar, sancion_vigente
from apps.fichas.models import Coincidencia, FichaAnimal
from apps.fichas.servicios import crear_ficha
from apps.imagenes.models import Fotografia
from apps.publicaciones.models import Publicacion
from apps.transito.models import PerfilTransito, Postulacion
from apps.transito.servicios import cupo_libre, hogar_habilitado

pytestmark = pytest.mark.django_db

PUNTO = Point(-68.31129, -54.80670, srid=4326)


@pytest.fixture(autouse=True)
def media_temporal(settings, tmp_path):
    """Las fotos de prueba van a una carpeta temporal, no a media/."""
    settings.MEDIA_ROOT = tmp_path


def cargar(**opciones):
    salida = StringIO()
    call_command("cargar_datos_prueba", password="clave-de-prueba", stdout=salida, **opciones)
    return salida.getvalue()


@pytest.fixture
def datos_viejos():
    """Un superusuario y una persona con una ficha, una publicación y una foto."""
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
    assert not Publicacion.objects.filter(descripcion="", ficha__nombre="Viejo").exists()
    assert not Fotografia.objects.filter(hash_sha256="0" * 64).exists()


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
    assert FichaAnimal.objects.filter(nombre="Nina").count() == 1


def ficha(nombre):
    return FichaAnimal.objects.get(nombre=nombre)


def test_todas_las_fotos_tienen_sus_creditos():
    creditos = (FOTOS / "CREDITOS.md").read_text()

    for archivo in FOTOS.glob("*.jpg"):
        assert f"`{archivo.name}`" in creditos, archivo.name


def test_las_publicaciones_quedan_en_ushuaia():
    cargar()

    for publicacion in Publicacion.objects.all():
        assert geo.en_zona(publicacion.ubicacion.x, publicacion.ubicacion.y), publicacion


def test_hay_publicaciones_de_cada_tipo_y_estado():
    cargar()

    vigentes = set(
        Publicacion.objects.filter(estado=Publicacion.Estado.VIGENTE).values_list("tipo", flat=True)
    )
    assert vigentes == {"extravio", "hallazgo", "adopcion", "transito"}
    estados = set(Publicacion.objects.values_list("estado", flat=True))
    assert estados == {"vigente", "resuelta", "eliminada"}
    assert Publicacion.objects.filter(etiqueta_urgente=True).exists()
    assert Publicacion.objects.exclude(telefono_visible="").exists()


def test_hay_coincidencias_en_cada_estado():
    cargar()

    elegidas = Coincidencia.objects.filter(elegida_por_autor=True)
    decisiones = set(elegidas.values_list("decision_responsable", flat=True))
    assert decisiones == {"pendiente", "confirmada", "descartada"}
    assert FichaAnimal.objects.filter(fusionada_en=ficha("Rocco")).exists()


def test_hay_fichas_privadas_y_una_foto_duplicada():
    cargar()

    assert ficha("Pipo").es_privada
    assert not ficha("Pipo").publicaciones.exists()
    assert Fotografia.objects.filter(motivo_revision=Fotografia.MotivoRevision.DUPLICADA).exists()


def test_cada_mascota_queda_en_un_paso_distinto_del_recorrido():
    cargar()
    pendientes = Postulacion.objects.filter(estado=Postulacion.Estado.PENDIENTE)

    assert ficha("Lola").estado == FichaAnimal.Estado.SIN_RESPONSABLE
    assert pendientes.filter(ficha=ficha("Toto"), tipo="transito").count() == 2
    assert Postulacion.objects.get(ficha=ficha("Nube"), tipo="transito").estado == "elegida"
    assert ficha("Rocky").estado == FichaAnimal.Estado.EN_TRANSITO
    assert pendientes.filter(ficha=ficha("Rocky"), tipo="adopcion").count() == 2
    assert Postulacion.objects.get(ficha=ficha("Mora"), tipo="adopcion").estado == "elegida"
    assert Adopcion.objects.filter(ficha=ficha("Simba"), adoptante=usuario("paula")).exists()


def test_un_hogar_queda_con_el_cupo_lleno():
    cargar()

    assert ficha("Coco").cuidador == usuario("diego")
    assert cupo_libre(PerfilTransito.objects.get(usuario=usuario("diego"))) == 0
