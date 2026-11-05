import pytest
from django.urls import reverse
from model_bakery import baker

from apps.cuentas.models import Rol
from apps.fichas.models import Coincidencia, FichaAnimal
from apps.publicaciones import vinculacion
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

pytestmark = pytest.mark.django_db


@pytest.fixture
def carla(django_user_model):
    return django_user_model.objects.create_user(
        "carla@ejemplo.com", "Carla", "clave-de-prueba-1", estado_cuenta="activa"
    )


@pytest.fixture
def moderador(django_user_model):
    return django_user_model.objects.create_user(
        "mod@ejemplo.com", "Mod", "clave-de-prueba-1", rol=Rol.MODERADOR, estado_cuenta="activa"
    )


def _coincidencia(autor, ficha, **campos):
    pub = hacer_publicacion(autor, tipo=Publicacion.Tipo.HALLAZGO, ficha=None)
    datos = {"elegida_por_autor": True, **campos}
    return baker.make(Coincidencia, publicacion=pub, ficha=ficha, **datos)


def test_el_responsable_ve_las_pendientes(ana, beto):
    ficha = baker.make(FichaAnimal, responsable=ana)
    c = _coincidencia(beto, ficha)
    assert list(vinculacion.pendientes_para(ana)) == [c]


def test_un_tercero_no_ve_nada(ana, beto, carla):
    c = _coincidencia(beto, baker.make(FichaAnimal, responsable=ana))
    assert c not in vinculacion.pendientes_para(carla)


def test_sin_responsable_las_ve_el_cuidador_y_el_moderador(beto, carla, moderador):
    ficha = baker.make(FichaAnimal, responsable=None, cuidador=carla)
    c = _coincidencia(beto, ficha)
    assert list(vinculacion.pendientes_para(carla)) == [c]
    assert list(vinculacion.pendientes_para(moderador)) == [c]


def test_el_moderador_no_ve_las_de_fichas_con_responsable(ana, beto, moderador):
    _coincidencia(beto, baker.make(FichaAnimal, responsable=ana))
    assert not vinculacion.pendientes_para(moderador).exists()


def test_no_aparecen_las_que_el_autor_no_eligio_ni_las_ya_decididas(ana, beto):
    ficha = baker.make(FichaAnimal, responsable=ana)
    _coincidencia(beto, ficha, elegida_por_autor=False)
    _coincidencia(beto, ficha, decision_responsable=Coincidencia.Decision.CONFIRMADA)
    assert not vinculacion.pendientes_para(ana).exists()


def test_la_pagina_lista_y_muestra_los_botones(entrar, ana, beto):
    _coincidencia(beto, baker.make(FichaAnimal, nombre="Nina", responsable=ana))
    html = entrar(ana).get(reverse("publicaciones:coincidencias")).content.decode()
    assert "Nina" in html and "Beto" in html
    assert "Sí, es el mismo" in html and "No es" in html


def test_la_pagina_sin_pendientes_lo_dice(entrar, carla):
    html = entrar(carla).get(reverse("publicaciones:coincidencias")).content.decode()
    assert "No tenés coincidencias pendientes" in html


def test_confirmar_desde_la_pagina_vuelve_a_la_lista(entrar, ana, beto):
    c = _coincidencia(beto, baker.make(FichaAnimal, responsable=ana))
    url = reverse("publicaciones:responder_coincidencia", args=[c.pk])
    respuesta = entrar(ana).post(url, {"accion": "confirmar"})
    assert respuesta.url == reverse("publicaciones:coincidencias")
    c.refresh_from_db()
    assert c.decision_responsable == Coincidencia.Decision.CONFIRMADA


def test_hay_que_iniciar_sesion(client):
    assert client.get(reverse("publicaciones:coincidencias")).status_code == 302
