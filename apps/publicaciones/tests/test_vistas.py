import pytest
from constance.test import override_config
from django.conf import settings
from django.urls import reverse
from model_bakery import baker

from apps.cuentas.models import EstadoCuenta, Rol
from apps.fichas.models import FichaAnimal
from apps.publicaciones.models import Publicacion

from .conftest import crear_imagen, hacer_publicacion

pytestmark = pytest.mark.django_db

URL = "publicaciones:publicar_extravio"


def datos(**cambios):
    base = {"especie": "perro", "nombre": "Firulais", "color": "negro", "foto": crear_imagen()}
    return {**base, **cambios}


def test_hay_que_iniciar_sesion(client):
    respuesta = client.get(reverse(URL))

    assert respuesta.status_code == 302
    assert respuesta.url.startswith(settings.LOGIN_URL)


def test_se_muestra_el_asistente(entrar, ana, con_domicilio):
    respuesta = entrar(ana).get(reverse(URL))

    assert respuesta.status_code == 200
    assert "Publicar extravío" in respuesta.content.decode()


def test_publica_un_animal_nuevo_y_muestra_la_publicacion(entrar, ana, con_domicilio):
    respuesta = entrar(ana).post(reverse(URL), datos())

    publicacion = Publicacion.objects.get()
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("publicaciones:detalle", args=[publicacion.pk])
    assert publicacion.ficha.responsable == ana


def test_publica_una_ficha_propia(entrar, ana, con_domicilio):
    ficha = baker.make(FichaAnimal, responsable=ana, especie="gato")

    respuesta = entrar(ana).post(reverse(URL), {"ficha": ficha.pk})

    assert respuesta.status_code == 302
    assert Publicacion.objects.get().ficha == ficha
    assert FichaAnimal.objects.count() == 1


def test_no_se_publica_con_la_ficha_de_otra_persona(entrar, ana, beto, con_domicilio):
    ajena = baker.make(FichaAnimal, responsable=beto)

    respuesta = entrar(ana).post(reverse(URL), {"ficha": ajena.pk})

    assert respuesta.status_code == 200
    assert not Publicacion.objects.exists()


def test_texto_ofensivo_se_rechaza(entrar, ana, con_domicilio):
    respuesta = entrar(ana).post(reverse(URL), datos(descripcion="mierda"))

    assert respuesta.status_code == 200
    assert "Texto ofensivo" in respuesta.content.decode()
    assert not Publicacion.objects.exists()
    assert not FichaAnimal.objects.exists()


def test_un_animal_nuevo_necesita_especie_y_foto(entrar, ana, con_domicilio):
    respuesta = entrar(ana).post(reverse(URL), {"nombre": "Sin datos"})

    html = respuesta.content.decode()
    assert respuesta.status_code == 200
    assert "Elegí la especie" in html
    assert "Subí una foto de la mascota" in html


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


def test_cualquier_usuario_con_sesion_ve_una_publicacion(entrar, ana, beto):
    publicacion = hacer_publicacion(ana, descripcion="Se perdió en el centro")

    respuesta = entrar(beto).get(reverse("publicaciones:detalle", args=[publicacion.pk]))

    assert respuesta.status_code == 200
    assert "Se perdió en el centro" in respuesta.content.decode()


def test_una_publicacion_eliminada_no_se_ve(entrar, ana):
    publicacion = hacer_publicacion(ana, estado=Publicacion.Estado.ELIMINADA)

    respuesta = entrar(ana).get(reverse("publicaciones:detalle", args=[publicacion.pk]))

    assert respuesta.status_code == 404


def test_un_domicilio_fuera_de_la_zona_se_informa_y_no_publica_nada(entrar, ana):
    respuesta = entrar(ana).post(reverse(URL), datos(latitud=-34.60, longitud=-58.38))

    assert respuesta.status_code == 200
    assert "Ushuaia" in respuesta.content.decode()
    assert not Publicacion.objects.exists()
    assert not FichaAnimal.objects.exists()


def test_un_visitante_ve_el_detalle_de_una_publicacion(client, ana):
    publicacion = hacer_publicacion(ana, ficha=None, descripcion="Se perdió cerca del puerto")

    respuesta = client.get(reverse("publicaciones:detalle", args=[publicacion.pk]))

    assert respuesta.status_code == 200
    html = respuesta.content.decode()
    assert "Se perdió cerca del puerto" in html and "Desvincular" not in html


def test_el_avistamiento_solo_lo_ven_el_autor_y_los_moderadores(
    client, entrar, ana, beto, django_user_model
):
    avistamiento = hacer_publicacion(ana, tipo=Publicacion.Tipo.SILVESTRE, ficha=None)
    url = reverse("publicaciones:detalle", args=[avistamiento.pk])
    moderador = django_user_model.objects.create_user(
        "mod@example.com",
        "Moni",
        "clave-segura-123",
        estado_cuenta=EstadoCuenta.ACTIVA,
        rol=Rol.MODERADOR,
    )

    assert client.get(url).status_code == 404  # visitante
    assert entrar(beto).get(url).status_code == 404  # otra persona
    assert entrar(ana).get(url).status_code == 200  # autora
    assert entrar(moderador).get(url).status_code == 200


def test_el_avistamiento_de_un_animal_peligroso_es_publico(client, ana):
    peligroso = hacer_publicacion(ana, tipo=Publicacion.Tipo.PELIGROSO, ficha=None)

    respuesta = client.get(reverse("publicaciones:detalle", args=[peligroso.pk]))

    assert respuesta.status_code == 200
