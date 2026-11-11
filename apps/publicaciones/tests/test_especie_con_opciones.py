import pytest
from django.urls import reverse

from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

pytestmark = pytest.mark.django_db


def test_los_listados_muestran_la_especie_con_su_nombre(client, ana):
    publicacion = hacer_publicacion(
        ana, tipo=Publicacion.Tipo.EXTRAVIO, ficha=None, especie="perro"
    )

    html = client.get(reverse("publicaciones:detalle", args=[publicacion.pk])).content.decode()

    assert "Perro" in html


def test_la_especie_solo_admite_las_del_catalogo():
    campo = Publicacion._meta.get_field("especie")

    assert ("perro", "Perro") in campo.choices
