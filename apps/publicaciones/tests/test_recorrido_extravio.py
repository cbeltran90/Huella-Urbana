"""Recorrido 2 de la demo: «extravío con coincidencia», de punta a punta."""

import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse

from apps.fichas.models import Coincidencia, FichaAnimal
from apps.fichas.servicios import crear_ficha
from apps.imagenes.models import Fotografia
from apps.publicaciones import servicios, vinculacion
from apps.publicaciones.models import Publicacion

from .conftest import crear_imagen, hacer_publicacion

pytestmark = pytest.mark.django_db

GATO_GRIS = {"especie": "gato", "tamano": "mediano", "raza": "mestizo", "color": "gris"}
PUNTO = Point(-68.2012, -54.8003, srid=4326)


@pytest.fixture
def camila(django_user_model):
    return django_user_model.objects.create_user(
        "camila@ejemplo.com", "Camila", "clave-de-prueba-1", estado_cuenta="activa"
    )


def test_hallazgo_con_coincidencia_vinculacion_y_confirmacion(entrar, ana, beto, camila):
    """Camila halla un gato gris; el sistema sugiere a Nina (de Ana) y a Pipo (de Beto)."""
    nina = crear_ficha(ana, {**GATO_GRIS, "nombre": "Nina"})
    hacer_publicacion(ana, tipo=Publicacion.Tipo.EXTRAVIO, ficha=nina, **GATO_GRIS)
    pipo = crear_ficha(beto, {**GATO_GRIS, "color": "atigrado", "nombre": "Pipo"})

    # 1. Camila publica el hallazgo y va derecho a las candidatas.
    cliente = entrar(camila)
    datos = {**GATO_GRIS, "latitud": -54.8003, "longitud": -68.2012, "foto": crear_imagen()}
    respuesta = cliente.post(reverse("publicaciones:publicar_hallazgo"), datos)
    hallazgo = Publicacion.objects.get(tipo=Publicacion.Tipo.HALLAZGO)
    assert respuesta.url == reverse("publicaciones:candidatas", args=[hallazgo.pk])

    # 2. Nina (4 de 4) antes que Pipo (3 de 4); la ficha privada no muestra su nombre.
    pagina = cliente.get(respuesta.url).content.decode()
    assert "Pipo" not in pagina
    coincidencias = list(hallazgo.coincidencias.all())
    assert [(c.ficha, c.atributos_coincidentes) for c in coincidencias] == [(nina, 4), (pipo, 3)]

    # 3. Camila elige a Nina: queda pendiente de la decisión de Ana.
    cliente.post(respuesta.url, {"ficha": nina.pk})
    coincidencia = Coincidencia.objects.get(publicacion=hallazgo, ficha=nina)
    assert coincidencia.elegida_por_autor
    assert coincidencia.decision_responsable == Coincidencia.Decision.PENDIENTE

    # 4. Ana confirma: el hallazgo queda en la ficha de Nina y la ficha nueva se fusiona.
    ficha_nueva = hallazgo.ficha
    url = reverse("publicaciones:responder_coincidencia", args=[coincidencia.pk])
    assert entrar(ana).post(url, {"accion": "confirmar"}).status_code == 302
    hallazgo.refresh_from_db()
    ficha_nueva.refresh_from_db()
    coincidencia.refresh_from_db()
    assert hallazgo.ficha == nina
    assert ficha_nueva.fusionada_en == nina
    assert coincidencia.decision_responsable == Coincidencia.Decision.CONFIRMADA
    assert Fotografia.objects.filter(ficha=nina).count() == 1


def test_primero_el_hallazgo_y_despues_el_extravio(ana, beto, con_domicilio):
    """Beto halló y tiene consigo al gato; Ana publica el extravío y Beto lo confirma."""
    hallazgo = servicios.publicar_hallazgo(
        beto, animal=GATO_GRIS, archivo=crear_imagen(), punto=PUNTO, tiene_consigo=True
    )
    extravio = servicios.publicar_extravio(ana, animal=GATO_GRIS, archivo=crear_imagen())
    ficha_ana, ficha_beto = extravio.ficha, hallazgo.ficha

    candidata = vinculacion.proponer_coincidencias(extravio)[0]
    assert candidata.ficha == ficha_beto and candidata.atributos_coincidentes == 4
    assert candidata.similitud_visual == pytest.approx(1.0)

    vinculacion.vincular(extravio, ficha_beto, ana)
    # Sin responsable decide quien lo tiene a cargo (Beto).
    vinculacion.responder(candidata, beto, confirmar=True)

    hallazgo.refresh_from_db()
    ficha_beto.refresh_from_db()
    ficha_ana.refresh_from_db()
    assert hallazgo.ficha == ficha_ana  # sobrevive la ficha de quien perdió al animal
    assert ficha_beto.fusionada_en == ficha_ana
    assert ficha_ana.cuidador == beto
    assert Fotografia.objects.filter(ficha=ficha_ana).count() == 2
    assert FichaAnimal.objects.get(pk=ficha_ana.pk).publicaciones.count() == 2
