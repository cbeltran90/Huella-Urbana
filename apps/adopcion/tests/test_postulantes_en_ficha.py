import pytest
from django.urls import reverse

from apps.fichas.models import FichaAnimal
from apps.transito.models import Postulacion

from .conftest import BACKEND_MODELO, con_perfil, hacer_ficha

pytestmark = pytest.mark.django_db


def ver_ficha(client, ficha, usuario):
    client.force_login(usuario, backend=BACKEND_MODELO)
    return client.get(reverse("fichas:detalle", args=[ficha.pk])).content.decode()


def postular(ficha, usuario, estado=Postulacion.Estado.PENDIENTE):
    return Postulacion.objects.create(
        ficha=ficha,
        usuario=usuario,
        tipo=Postulacion.Tipo.ADOPCION,
        estado=estado,
        contacto="2901 444444",
    )


def test_quien_elige_ve_cuantos_se_postularon(client, ana, beto, carla):
    ficha = hacer_ficha(cuidador=beto)
    postular(ficha, con_perfil(ana))
    postular(ficha, con_perfil(carla))

    html = ver_ficha(client, ficha, beto)

    assert "Se postularon 2 personas para adoptar." in html
    assert reverse("adopcion:postulantes", args=[ficha.pk]) in html


def test_con_una_sola_persona_habla_en_singular(client, ana, beto):
    ficha = hacer_ficha(cuidador=beto)
    postular(ficha, con_perfil(ana))

    assert "Se postuló 1 persona para adoptar." in ver_ficha(client, ficha, beto)


def test_sin_postulantes_lo_dice(client, beto):
    html = ver_ficha(client, hacer_ficha(cuidador=beto), beto)

    assert "Todavía no se postuló nadie para adoptar." in html


def test_si_ya_eligio_muestra_a_quien(client, ana, beto):
    ficha = hacer_ficha(cuidador=beto)
    postular(ficha, con_perfil(ana), Postulacion.Estado.ELEGIDA)

    assert "Elegiste a Ana para adoptar." in ver_ficha(client, ficha, beto)


def test_los_demas_no_ven_el_panel(client, ana, beto, carla):
    ficha = hacer_ficha(cuidador=beto)
    postular(ficha, con_perfil(ana))

    html = ver_ficha(client, ficha, carla)

    assert "para adoptar." not in html
    assert reverse("adopcion:postulantes", args=[ficha.pk]) not in html


def test_si_no_esta_disponible_no_se_ve(client, beto):
    html = ver_ficha(client, hacer_ficha(FichaAnimal.Estado.REGISTRADO, cuidador=beto), beto)

    assert "Todavía no se postuló nadie" not in html
