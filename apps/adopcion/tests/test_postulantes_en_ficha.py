import pytest
from django.urls import reverse
from model_bakery import baker

from apps.adopcion.models import Adopcion
from apps.cuentas.models import Rol
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


def test_con_alguien_elegido_ofrece_concretar_o_cancelar(client, ana, beto):
    ficha = hacer_ficha(cuidador=beto)
    postular(ficha, con_perfil(ana), Postulacion.Estado.ELEGIDA)

    html = ver_ficha(client, ficha, beto)

    assert "Adopción en curso con Ana." in html
    assert reverse("adopcion:concretar", args=[ficha.pk]) in html
    assert reverse("adopcion:cancelar", args=[ficha.pk]) in html


def test_un_moderador_ve_la_adopcion_en_curso(client, ana, beto, carla):
    carla.rol = Rol.MODERADOR
    carla.save()
    ficha = hacer_ficha(cuidador=beto)
    postular(ficha, con_perfil(ana), Postulacion.Estado.ELEGIDA)

    assert reverse("adopcion:concretar", args=[ficha.pk]) in ver_ficha(client, ficha, carla)


def test_sin_elegido_el_moderador_no_ve_el_panel_si_hay_alguien_a_cargo(client, ana, beto, carla):
    carla.rol = Rol.MODERADOR
    carla.save()
    ficha = hacer_ficha(cuidador=beto)
    postular(ficha, con_perfil(ana))

    assert "Se postuló 1 persona" not in ver_ficha(client, ficha, carla)


def test_los_demas_no_ven_el_panel(client, ana, beto, carla):
    ficha = hacer_ficha(cuidador=beto)
    postular(ficha, con_perfil(ana))

    html = ver_ficha(client, ficha, carla)

    assert "para adoptar." not in html
    assert reverse("adopcion:postulantes", args=[ficha.pk]) not in html


def test_si_no_esta_disponible_no_se_ve(client, beto):
    html = ver_ficha(client, hacer_ficha(FichaAnimal.Estado.REGISTRADO, cuidador=beto), beto)

    assert "Todavía no se postuló nadie" not in html


def test_al_volver_de_concretar_confirma_la_adopcion(client, ana, beto):
    ficha = hacer_ficha(FichaAnimal.Estado.REGISTRADO, responsable=ana)
    baker.make(Adopcion, ficha=ficha, adoptante=ana, entregado_por=beto)
    client.force_login(beto, backend=BACKEND_MODELO)

    url = reverse("fichas:detalle", args=[ficha.pk]) + "?adoptada=1"
    html = client.get(url).content.decode()

    assert "¡Listo! La adopción quedó registrada." in html
    assert "Ana" not in html.split("¡Listo!")[1].split("</p>")[0]


def test_sin_adopcion_el_cartel_no_aparece(client, beto):
    ficha = hacer_ficha(cuidador=beto)
    client.force_login(beto, backend=BACKEND_MODELO)

    url = reverse("fichas:detalle", args=[ficha.pk]) + "?adoptada=1"

    assert "¡Listo!" not in client.get(url).content.decode()
