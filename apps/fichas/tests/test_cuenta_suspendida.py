import pytest
from django.urls import reverse
from model_bakery import baker

from apps.cuentas.models import Sancion
from apps.fichas.models import FichaAnimal

pytestmark = pytest.mark.django_db


@pytest.fixture
def suspendida(ana):
    Sancion.objects.create(
        usuario=ana,
        email_hash=ana.email_hash,
        tipo=Sancion.Tipo.PERMANENTE,
        motivo="Motivo de prueba",
    )
    return ana


def test_una_cuenta_suspendida_no_puede_crear_fichas(entrar, suspendida):
    cliente = entrar(suspendida)

    assert cliente.get(reverse("fichas:nueva")).status_code == 403
    assert cliente.post(reverse("fichas:nueva"), {"especie": "perro"}).status_code == 403
    assert not FichaAnimal.objects.exists()


def test_una_cuenta_suspendida_no_puede_editar(entrar, suspendida):
    ficha = baker.make(FichaAnimal, responsable=suspendida, nombre="Viejo", especie="perro")

    respuesta = entrar(suspendida).post(
        reverse("fichas:editar", args=[ficha.pk]), {"especie": "perro", "nombre": "Nuevo"}
    )

    ficha.refresh_from_db()
    assert respuesta.status_code == 403
    assert ficha.nombre == "Viejo"


def test_una_cuenta_suspendida_no_puede_dar_de_baja(entrar, suspendida):
    ficha = baker.make(FichaAnimal, responsable=suspendida, estado=FichaAnimal.Estado.REGISTRADO)

    respuesta = entrar(suspendida).post(reverse("fichas:baja", args=[ficha.pk]))

    assert respuesta.status_code == 403
    assert FichaAnimal.objects.filter(pk=ficha.pk).exists()


def test_una_cuenta_suspendida_sigue_viendo_sus_fichas(entrar, suspendida):
    ficha = baker.make(FichaAnimal, responsable=suspendida, estado=FichaAnimal.Estado.REGISTRADO)
    cliente = entrar(suspendida)

    assert cliente.get(reverse("fichas:mis_fichas")).status_code == 200
    detalle = cliente.get(reverse("fichas:detalle", args=[ficha.pk]))
    assert detalle.status_code == 200


def test_el_detalle_no_ofrece_editar_ni_dar_de_baja_a_una_cuenta_suspendida(entrar, suspendida):
    ficha = baker.make(FichaAnimal, responsable=suspendida, estado=FichaAnimal.Estado.REGISTRADO)

    html = entrar(suspendida).get(reverse("fichas:detalle", args=[ficha.pk])).content.decode()

    assert reverse("fichas:editar", args=[ficha.pk]) not in html
    assert reverse("fichas:baja", args=[ficha.pk]) not in html


def test_una_cuenta_sin_sancion_si_ve_los_botones(entrar, ana):
    ficha = baker.make(FichaAnimal, responsable=ana, estado=FichaAnimal.Estado.REGISTRADO)

    html = entrar(ana).get(reverse("fichas:detalle", args=[ficha.pk])).content.decode()

    assert reverse("fichas:editar", args=[ficha.pk]) in html
    assert reverse("fichas:baja", args=[ficha.pk]) in html


def test_mis_fichas_no_ofrece_crear_a_una_cuenta_suspendida(entrar, suspendida):
    html = entrar(suspendida).get(reverse("fichas:mis_fichas")).content.decode()

    assert reverse("fichas:nueva") not in html
    assert "Creá la primera" not in html


def test_mis_fichas_ofrece_crear_a_una_cuenta_sin_sancion(entrar, ana):
    html = entrar(ana).get(reverse("fichas:mis_fichas")).content.decode()

    assert reverse("fichas:nueva") in html
    assert "Creá la primera" in html
