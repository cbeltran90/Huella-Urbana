import pytest
from django.conf import settings
from django.urls import reverse
from model_bakery import baker

from apps.fichas.models import FichaAnimal

Estado = FichaAnimal.Estado

pytestmark = pytest.mark.django_db


def datos_ficha(**cambios):
    base = {
        "especie": "perro",
        "nombre": "Firulais",
        "tamano": "mediano",
        "edad_estimada": "3",
        "color": "marrón",
        "raza": "mestizo",
    }
    return {**base, **cambios}


def test_hay_que_iniciar_sesion(client):
    respuesta = client.get(reverse("fichas:mis_fichas"))

    assert respuesta.status_code == 302
    assert respuesta.url.startswith(settings.LOGIN_URL)


def test_mis_fichas_lista_las_propias_y_las_que_tiene_a_cargo(entrar, ana, beto, carla):
    baker.make(FichaAnimal, nombre="Firulais", responsable=ana)
    baker.make(FichaAnimal, nombre="Garfield", responsable=beto, cuidador=ana)
    baker.make(FichaAnimal, nombre="Ajeno", responsable=carla)

    html = entrar(ana).get(reverse("fichas:mis_fichas")).content.decode()

    assert "Firulais" in html
    assert "Garfield" in html
    assert "Ajeno" not in html


def test_el_alta_crea_una_ficha_privada_y_vuelve_a_mis_fichas(entrar, ana):
    respuesta = entrar(ana).post(reverse("fichas:nueva"), datos_ficha())

    assert respuesta.status_code == 302
    assert respuesta.url == reverse("fichas:mis_fichas")
    ficha = FichaAnimal.objects.get()
    assert ficha.responsable == ana
    assert ficha.estado == Estado.REGISTRADO
    assert ficha.es_privada is True


def test_el_alta_con_texto_ofensivo_no_crea_nada(entrar, ana):
    respuesta = entrar(ana).post(reverse("fichas:nueva"), datos_ficha(nombre="mierda"))

    assert respuesta.status_code == 200
    assert "Texto ofensivo" in respuesta.content.decode()
    assert not FichaAnimal.objects.exists()


def test_una_ficha_privada_de_otra_persona_no_se_ve(entrar, ana, beto):
    ficha = baker.make(FichaAnimal, responsable=ana, es_privada=True)

    respuesta = entrar(beto).get(reverse("fichas:detalle", args=[ficha.pk]))

    assert respuesta.status_code == 404


def test_el_responsable_y_el_moderador_ven_la_ficha_privada(entrar, ana, moderador):
    ficha = baker.make(FichaAnimal, nombre="Firulais", responsable=ana, es_privada=True)
    url = reverse("fichas:detalle", args=[ficha.pk])

    assert entrar(ana).get(url).status_code == 200
    assert entrar(moderador).get(url).status_code == 200


def test_editar_cambia_los_datos(entrar, ana):
    ficha = baker.make(FichaAnimal, responsable=ana, nombre="Viejo", especie="perro")

    respuesta = entrar(ana).post(
        reverse("fichas:editar", args=[ficha.pk]), datos_ficha(nombre="Nuevo")
    )

    assert respuesta.status_code == 302
    ficha.refresh_from_db()
    assert ficha.nombre == "Nuevo"


def test_quien_la_tiene_a_cargo_puede_editar(entrar, ana, beto):
    ficha = baker.make(FichaAnimal, responsable=ana, cuidador=beto, especie="perro")

    respuesta = entrar(beto).get(reverse("fichas:editar", args=[ficha.pk]))

    assert respuesta.status_code == 200


def test_una_persona_ajena_no_puede_editar_una_ficha_publica(entrar, ana, carla):
    ficha = baker.make(FichaAnimal, responsable=ana, es_privada=False)

    respuesta = entrar(carla).get(reverse("fichas:editar", args=[ficha.pk]))

    assert respuesta.status_code == 403


def test_la_baja_pide_confirmacion_y_despues_borra(entrar, ana):
    ficha = baker.make(FichaAnimal, responsable=ana, estado=Estado.REGISTRADO)
    cliente = entrar(ana)
    url = reverse("fichas:baja", args=[ficha.pk])

    assert cliente.get(url).status_code == 200
    assert FichaAnimal.objects.filter(pk=ficha.pk).exists()

    assert cliente.post(url).status_code == 302
    assert not FichaAnimal.objects.filter(pk=ficha.pk).exists()


def test_quien_la_tiene_a_cargo_no_puede_dar_de_baja(entrar, ana, beto):
    ficha = baker.make(FichaAnimal, responsable=ana, cuidador=beto, estado=Estado.REGISTRADO)

    respuesta = entrar(beto).post(reverse("fichas:baja", args=[ficha.pk]))

    assert respuesta.status_code == 403
    assert FichaAnimal.objects.filter(pk=ficha.pk).exists()


def test_no_se_da_de_baja_una_ficha_que_esta_en_adopcion(entrar, ana):
    ficha = baker.make(FichaAnimal, responsable=ana, estado=Estado.EN_ADOPCION)

    respuesta = entrar(ana).post(reverse("fichas:baja", args=[ficha.pk]))

    assert respuesta.status_code == 403
    assert FichaAnimal.objects.filter(pk=ficha.pk).exists()
