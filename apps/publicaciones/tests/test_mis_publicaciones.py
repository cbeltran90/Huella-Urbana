from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from apps.fichas.models import FichaAnimal
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

Tipo, Estado = Publicacion.Tipo, Publicacion.Estado
MIS_PUBLICACIONES = reverse("publicaciones:mis_publicaciones")

pytestmark = pytest.mark.django_db


def test_muestra_solo_mis_publicaciones_vigentes(entrar, ana, beto):
    hacer_publicacion(ana, descripcion="Mía vigente")
    hacer_publicacion(ana, descripcion="Mía resuelta", estado=Estado.RESUELTA)
    hacer_publicacion(ana, descripcion="Mía eliminada", estado=Estado.ELIMINADA)
    hacer_publicacion(beto, descripcion="De Beto")

    html = entrar(ana).get(MIS_PUBLICACIONES).content.decode()

    assert "Mía vigente" in html
    assert "Mía resuelta" not in html
    assert "Mía eliminada" not in html
    assert "De Beto" not in html


def test_las_mas_nuevas_primero(entrar, ana):
    hacer_publicacion(ana, descripcion="La vieja", fecha=timezone.now() - timedelta(days=3))
    hacer_publicacion(ana, descripcion="La nueva")

    html = entrar(ana).get(MIS_PUBLICACIONES).content.decode()

    assert html.index("La nueva") < html.index("La vieja")


def test_sin_publicaciones_lo_dice(entrar, ana):
    assert "No tenés publicaciones abiertas" in entrar(ana).get(MIS_PUBLICACIONES).content.decode()


def test_pide_ingresar(client):
    respuesta = client.get(MIS_PUBLICACIONES)

    assert respuesta.status_code == 302
    assert respuesta.url.startswith(reverse("cuentas:login"))


def test_el_menu_lleva_a_mis_publicaciones(entrar, ana):
    html = entrar(ana).get(reverse("core:inicio")).content.decode()

    assert MIS_PUBLICACIONES in html


def test_retirar_un_extravio_lo_saca_de_mis_publicaciones(entrar, ana):
    ficha = baker.make(FichaAnimal, especie="perro", responsable=ana)
    hacer_publicacion(ana, tipo=Tipo.EXTRAVIO, ficha=ficha, descripcion="Se perdió Toby")
    cliente = entrar(ana)
    retirar = reverse("publicaciones:resolver_caso", args=[ficha.pk])

    assert retirar in cliente.get(MIS_PUBLICACIONES).content.decode()
    cliente.post(retirar)
    assert "Se perdió Toby" not in cliente.get(MIS_PUBLICACIONES).content.decode()


def test_explica_por_que_no_se_puede_retirar(entrar, ana):
    sin_responsable = baker.make(FichaAnimal, especie="gato", responsable=None)
    hacer_publicacion(ana, tipo=Tipo.HALLAZGO, ficha=sin_responsable)
    hacer_publicacion(ana, tipo=Tipo.ADOPCION)

    html = entrar(ana).get(MIS_PUBLICACIONES).content.decode()

    assert "Este caso lo cierra un moderador." in html
    assert "Se cierra sola cuando el animal consiga un hogar." in html
    assert reverse("publicaciones:resolver_caso", args=[sin_responsable.pk]) not in html
