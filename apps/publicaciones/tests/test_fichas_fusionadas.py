import pytest
from django.urls import reverse
from model_bakery import baker

from apps.fichas.comparacion import buscar_candidatas
from apps.fichas.models import Coincidencia, FichaAnimal
from apps.publicaciones import vinculacion
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

pytestmark = pytest.mark.django_db


@pytest.fixture
def fusionada(ana, beto):
    """Beto encontró un gato (ficha sobrante, a su cargo); Ana lo reconoce como suyo."""
    principal = baker.make(FichaAnimal, responsable=ana, estado=FichaAnimal.Estado.REGISTRADO)
    sobrante = baker.make(
        FichaAnimal,
        responsable=None,
        cuidador=beto,
        cuidador_contacto="2901-555555",
        estado=FichaAnimal.Estado.SIN_RESPONSABLE,
        sin_responsable_desde="2026-11-01",
    )
    hallazgo = hacer_publicacion(beto, tipo=Publicacion.Tipo.HALLAZGO, ficha=sobrante)
    coincidencia = baker.make(
        Coincidencia, publicacion=hallazgo, ficha=principal, elegida_por_autor=True
    )
    vinculacion.responder(coincidencia, ana, confirmar=True)
    sobrante.refresh_from_db()
    return principal, sobrante


def test_la_sobrante_queda_sin_cuidador_ni_plazo(fusionada):
    principal, sobrante = fusionada

    assert sobrante.fusionada_en == principal
    assert sobrante.cuidador is None and sobrante.cuidador_contacto == ""
    assert sobrante.sin_responsable_desde is None


def test_la_sobrante_no_aparece_en_mis_fichas(entrar, beto, fusionada):
    _, sobrante = fusionada

    html = entrar(beto).get(reverse("fichas:mis_fichas")).content.decode()

    assert reverse("fichas:detalle", args=[sobrante.pk]) not in html


def test_la_sobrante_no_es_candidata(ana):
    atributos = {"especie": "gato", "color": "gris", "tamano": "pequeno"}
    fusionada = baker.make(FichaAnimal, responsable=ana, **atributos)
    hacer_publicacion(ana, tipo=Publicacion.Tipo.EXTRAVIO, ficha=fusionada, **atributos)
    hallazgo = hacer_publicacion(ana, tipo=Publicacion.Tipo.HALLAZGO, ficha=None, **atributos)
    assert [c[0] for c in buscar_candidatas(hallazgo)] == [fusionada]  # antes de fusionarla

    otra = baker.make(FichaAnimal, responsable=ana)
    FichaAnimal.objects.filter(pk=fusionada.pk).update(fusionada_en=otra)

    assert buscar_candidatas(hallazgo) == []
