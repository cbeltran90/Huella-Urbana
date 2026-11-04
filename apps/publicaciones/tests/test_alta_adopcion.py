import sys
import types

import pytest
from constance.test import override_config
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.fichas.models import FichaAnimal
from apps.imagenes.models import Fotografia
from apps.imagenes.procesamiento import ImagenInvalida
from apps.publicaciones import avisos, servicios, ubicacion
from apps.publicaciones.forms import MAX_FOTOS
from apps.publicaciones.models import Publicacion

from .conftest import crear_imagen, hacer_publicacion

pytestmark = pytest.mark.django_db

URL = "publicaciones:alta_adopcion"
ANIMAL = {"especie": "perro", "tamano": "mediano", "nombre": "Firulais", "color": "negro"}


def datos(**cambios):
    base = {"especie": "perro", "nombre": "Firulais", "fotos": [crear_imagen(), crear_imagen()]}
    return {**base, **cambios}


@pytest.fixture
def modulos_de_otros(monkeypatch):
    """Simula "hogares_compatibles" y "notificar" y anota a quién se avisó."""
    avisados = []
    transito = types.ModuleType("apps.transito.servicios")
    notificaciones = types.ModuleType("apps.notificaciones.servicios")
    transito.hogares_compatibles = lambda ficha: []
    notificaciones.notificar = lambda usuario, tipo, titulo, mensaje="", **kw: avisados.append(
        (usuario, tipo, kw)
    )
    monkeypatch.setitem(sys.modules, "apps.transito.servicios", transito)
    monkeypatch.setitem(sys.modules, "apps.notificaciones.servicios", notificaciones)
    return types.SimpleNamespace(
        transito=transito, notificaciones=notificaciones, avisados=avisados
    )


# --- servicio ---


def test_crea_la_ficha_en_adopcion_y_su_publicacion(ana, con_domicilio):
    publicacion = servicios.alta_en_adopcion(ana, animal=ANIMAL, archivos=[crear_imagen()])

    ficha = publicacion.ficha
    assert ficha.estado == FichaAnimal.Estado.EN_ADOPCION
    assert ficha.cuidador == ana
    assert publicacion.tipo == Publicacion.Tipo.ADOPCION
    assert publicacion.estado == Publicacion.Estado.VIGENTE
    assert publicacion.autor == ana
    assert publicacion.especie == "perro"


def test_la_publicacion_sale_con_la_ubicacion_del_domicilio(ana, con_domicilio):
    publicacion = servicios.alta_en_adopcion(ana, animal=ANIMAL, archivos=[crear_imagen()])

    assert publicacion.ubicacion.equals_exact(con_domicilio, 1e-9)


def test_todas_las_fotos_son_de_la_ficha(ana, con_domicilio):
    publicacion = servicios.alta_en_adopcion(
        ana, animal=ANIMAL, archivos=[crear_imagen(), crear_imagen()]
    )

    assert Fotografia.objects.filter(ficha=publicacion.ficha).count() == 2


def test_guarda_el_telefono_visible(ana, con_domicilio):
    publicacion = servicios.alta_en_adopcion(
        ana, animal=ANIMAL, archivos=[crear_imagen()], telefono_visible="2901 555555"
    )

    assert publicacion.telefono_visible == "2901 555555"


def test_sin_domicilio_se_usa_el_punto_indicado_pero_se_publica_el_desplazado(ana, monkeypatch):
    exacto = Point(-68.3030, -54.8019, srid=4326)
    desplazado = Point(-68.3031, -54.8020, srid=4326)
    guardados = []
    monkeypatch.setattr(ubicacion, "punto_de_domicilio", lambda usuario: None)
    monkeypatch.setattr(
        ubicacion,
        "registrar_domicilio",
        lambda usuario, punto: guardados.append(punto) or desplazado,
    )

    publicacion = servicios.alta_en_adopcion(
        ana, animal=ANIMAL, archivos=[crear_imagen()], punto=exacto
    )

    assert guardados == [exacto]
    assert publicacion.ubicacion.equals_exact(desplazado, 1e-9)


def test_sin_domicilio_ni_punto_no_se_publica(ana, monkeypatch):
    monkeypatch.setattr(ubicacion, "punto_de_domicilio", lambda usuario: None)

    with pytest.raises(ValueError):
        servicios.alta_en_adopcion(ana, animal=ANIMAL, archivos=[crear_imagen()])

    assert not FichaAnimal.objects.exists()


def test_sin_fotos_no_se_publica(ana, con_domicilio):
    with pytest.raises(ValueError):
        servicios.alta_en_adopcion(ana, animal=ANIMAL, archivos=[])

    assert not FichaAnimal.objects.exists()


def test_una_foto_invalida_no_deja_nada_a_medias(ana, con_domicilio):
    mala = SimpleUploadedFile("a.jpg", b"no es una imagen")

    with pytest.raises(ImagenInvalida):
        servicios.alta_en_adopcion(ana, animal=ANIMAL, archivos=[crear_imagen(), mala])

    assert not FichaAnimal.objects.exists()
    assert not Publicacion.objects.exists()
    assert not Fotografia.objects.exists()


# --- avisos a hogares compatibles ---


def test_avisa_a_los_hogares_compatibles_menos_al_autor(ana, beto, con_domicilio, modulos_de_otros):
    modulos_de_otros.transito.hogares_compatibles = lambda ficha: [beto, ana]

    publicacion = servicios.alta_en_adopcion(ana, animal=ANIMAL, archivos=[crear_imagen()])

    assert [aviso[0] for aviso in modulos_de_otros.avisados] == [beto]
    assert modulos_de_otros.avisados[0][2]["publicacion"] == publicacion


def test_acepta_perfiles_de_hogar_con_su_usuario(ana, beto, con_domicilio, modulos_de_otros):
    perfil = types.SimpleNamespace(usuario=beto)
    modulos_de_otros.transito.hogares_compatibles = lambda ficha: [perfil]

    servicios.alta_en_adopcion(ana, animal=ANIMAL, archivos=[crear_imagen()])

    assert [aviso[0] for aviso in modulos_de_otros.avisados] == [beto]


def test_si_avisar_falla_el_alta_queda_igual(ana, beto, con_domicilio, modulos_de_otros):
    def falla(*args, **kwargs):
        raise RuntimeError("caído")

    modulos_de_otros.transito.hogares_compatibles = lambda ficha: [beto]
    modulos_de_otros.notificaciones.notificar = falla

    publicacion = servicios.alta_en_adopcion(ana, animal=ANIMAL, archivos=[crear_imagen()])

    assert publicacion.pk is not None


def test_si_faltan_los_modulos_de_otros_no_se_avisa_a_nadie(ana, con_domicilio, monkeypatch):
    monkeypatch.setitem(sys.modules, "apps.transito.servicios", None)
    monkeypatch.setitem(sys.modules, "apps.notificaciones.servicios", None)

    publicacion = servicios.alta_en_adopcion(ana, animal=ANIMAL, archivos=[crear_imagen()])

    assert avisos.avisar_hogares_compatibles(publicacion) == 0


# --- vista ---


def test_hay_que_iniciar_sesion(client):
    respuesta = client.get(reverse(URL))

    assert respuesta.status_code == 302
    assert respuesta.url.startswith(settings.LOGIN_URL)


def test_se_muestra_el_asistente(entrar, ana, con_domicilio):
    respuesta = entrar(ana).get(reverse(URL))

    assert respuesta.status_code == 200
    assert "en adopción" in respuesta.content.decode()


def test_da_de_alta_y_muestra_la_publicacion(entrar, ana, con_domicilio):
    respuesta = entrar(ana).post(reverse(URL), datos())

    publicacion = Publicacion.objects.get()
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("publicaciones:detalle", args=[publicacion.pk])
    assert publicacion.ficha.estado == FichaAnimal.Estado.EN_ADOPCION
    assert Fotografia.objects.count() == 2


def test_texto_ofensivo_en_la_ficha_o_la_descripcion_se_rechaza(entrar, ana, con_domicilio):
    cliente = entrar(ana)

    for campo in ("nombre", "descripcion"):
        respuesta = cliente.post(reverse(URL), datos(**{campo: "mierda"}))
        assert respuesta.status_code == 200
        assert "Texto ofensivo" in respuesta.content.decode()

    assert not Publicacion.objects.exists()
    assert not FichaAnimal.objects.exists()


def test_hace_falta_al_menos_una_foto(entrar, ana, con_domicilio):
    respuesta = entrar(ana).post(reverse(URL), datos(fotos=[]))

    assert respuesta.status_code == 200
    assert "Subí al menos una foto" in respuesta.content.decode()
    assert not Publicacion.objects.exists()


def test_hay_un_maximo_de_fotos(entrar, ana, con_domicilio):
    fotos = [crear_imagen() for _ in range(MAX_FOTOS + 1)]

    respuesta = entrar(ana).post(reverse(URL), datos(fotos=fotos))

    assert respuesta.status_code == 200
    assert "hasta" in respuesta.content.decode()
    assert not Publicacion.objects.exists()


def test_el_telefono_tiene_que_ser_valido(entrar, ana, con_domicilio):
    respuesta = entrar(ana).post(reverse(URL), datos(telefono_visible="hola"))

    assert respuesta.status_code == 200
    assert "Ingresá un teléfono válido" in respuesta.content.decode()


def test_sin_domicilio_hay_que_indicar_la_ubicacion(entrar, ana):
    respuesta = entrar(ana).post(reverse(URL), datos())

    assert respuesta.status_code == 200
    assert "Indicá tu ubicación" in respuesta.content.decode()
    assert not Publicacion.objects.exists()


@override_config(MAX_PUBLICACIONES_HORA=1)
def test_el_limite_por_hora_responde_403(entrar, ana, con_domicilio):
    hacer_publicacion(ana)

    respuesta = entrar(ana).post(reverse(URL), datos())

    assert respuesta.status_code == 403
    assert Publicacion.objects.count() == 1
