import pytest
from django.urls import reverse
from model_bakery import baker

from apps.fichas.models import FichaAnimal
from apps.imagenes.models import Fotografia

pytestmark = pytest.mark.django_db


def test_la_ficha_fusionada_lleva_a_la_principal_con_un_aviso(entrar, ana):
    principal = baker.make(FichaAnimal, responsable=ana, especie="gato", nombre="Michi")
    sobrante = baker.make(FichaAnimal, responsable=ana, especie="gato", fusionada_en=principal)

    respuesta = entrar(ana).get(reverse("fichas:detalle", args=[sobrante.pk]), follow=True)

    assert (
        respuesta.redirect_chain[0][0]
        == f"{reverse('fichas:detalle', args=[principal.pk])}?unida=1"
    )
    assert "Michi" in respuesta.content.decode()
    assert "se unió a esta" in respuesta.content.decode()


def test_la_ficha_fusionada_sigue_la_cadena_hasta_la_principal(entrar, ana):
    final = baker.make(FichaAnimal, responsable=ana, especie="gato")
    media = baker.make(FichaAnimal, responsable=ana, especie="gato", fusionada_en=final)
    primera = baker.make(FichaAnimal, responsable=ana, especie="gato", fusionada_en=media)

    respuesta = entrar(ana).get(reverse("fichas:detalle", args=[primera.pk]))

    assert respuesta.url.startswith(reverse("fichas:detalle", args=[final.pk]))


def test_una_ficha_normal_no_redirige_ni_muestra_el_aviso(entrar, ana):
    ficha = baker.make(FichaAnimal, responsable=ana, especie="gato")

    respuesta = entrar(ana).get(reverse("fichas:detalle", args=[ficha.pk]))

    assert respuesta.status_code == 200
    assert "se unió a esta" not in respuesta.content.decode()


def test_la_foto_se_ve_en_el_detalle(entrar, ana):
    ficha = baker.make(FichaAnimal, responsable=ana, especie="perro")
    foto = baker.make(Fotografia, ficha=ficha, archivo="fichas/rex.jpg")

    html = entrar(ana).get(reverse("fichas:detalle", args=[ficha.pk])).content.decode()

    assert foto.archivo in html


def test_la_foto_marcada_para_revision_no_se_muestra_a_los_visitantes(client):
    ficha = baker.make(FichaAnimal, es_privada=False, especie="perro")
    baker.make(Fotografia, ficha=ficha, archivo="fichas/ok.jpg")
    baker.make(
        Fotografia,
        ficha=ficha,
        archivo="fichas/marcada.jpg",
        motivo_revision=Fotografia.MotivoRevision.DUPLICADA,
    )

    html = client.get(reverse("fichas:detalle", args=[ficha.pk])).content.decode()

    assert "fichas/ok.jpg" in html and "fichas/marcada.jpg" not in html


def test_volver_lleva_a_la_pagina_anterior(entrar, ana):
    ficha = baker.make(FichaAnimal, responsable=ana, especie="gato")

    respuesta = entrar(ana).get(
        reverse("fichas:detalle", args=[ficha.pk]), HTTP_REFERER="http://testserver/mapa/"
    )

    assert respuesta.context["volver"] == "http://testserver/mapa/"


def test_volver_sin_pagina_anterior_lleva_a_mis_fichas(entrar, ana):
    ficha = baker.make(FichaAnimal, responsable=ana, especie="gato")

    respuesta = entrar(ana).get(reverse("fichas:detalle", args=[ficha.pk]))

    assert respuesta.context["volver"] == reverse("fichas:mis_fichas")


def test_volver_ignora_una_pagina_anterior_de_otro_sitio(entrar, ana):
    ficha = baker.make(FichaAnimal, responsable=ana, especie="gato")

    respuesta = entrar(ana).get(
        reverse("fichas:detalle", args=[ficha.pk]), HTTP_REFERER="https://otro-sitio.com/x"
    )

    assert respuesta.context["volver"] == reverse("fichas:mis_fichas")
