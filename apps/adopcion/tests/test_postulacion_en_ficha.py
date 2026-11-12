import pytest
from django.urls import reverse

from apps.fichas.models import FichaAnimal
from apps.transito.models import Postulacion

from .conftest import BACKEND_MODELO, con_perfil, hacer_ficha

Estado = FichaAnimal.Estado

pytestmark = pytest.mark.django_db

BOTON = "Postularme para adoptar"


def ver_ficha(client, ficha, usuario=None, consulta=""):
    if usuario is not None:
        client.force_login(usuario, backend=BACKEND_MODELO)
    url = reverse("fichas:detalle", args=[ficha.pk]) + consulta
    return client.get(url).content.decode()


def postulacion(ficha, usuario, tipo=Postulacion.Tipo.ADOPCION):
    return Postulacion.objects.create(
        ficha=ficha, usuario=usuario, tipo=tipo, contacto="2901 444444"
    )


def test_un_visitante_ve_el_boton(client):
    ficha = hacer_ficha()

    html = ver_ficha(client, ficha)

    assert BOTON in html
    assert reverse("adopcion:postular", args=[ficha.pk]) in html


@pytest.mark.parametrize("estado", [Estado.EN_ADOPCION, Estado.EN_TRANSITO])
def test_quien_puede_postularse_ve_el_boton(client, ana, estado):
    assert BOTON in ver_ficha(client, hacer_ficha(estado), con_perfil(ana))


def test_sin_perfil_tambien_ve_el_boton(client, ana):
    assert BOTON in ver_ficha(client, hacer_ficha(), ana)


def test_el_duenio_no_ve_el_boton(client, ana):
    assert BOTON not in ver_ficha(client, hacer_ficha(responsable=ana), con_perfil(ana))


def test_si_no_esta_disponible_no_se_ve(client, ana):
    assert BOTON not in ver_ficha(client, hacer_ficha(Estado.REGISTRADO), con_perfil(ana))


def test_con_su_postulacion_pendiente_la_ve_y_puede_retirarla(client, ana):
    ficha = hacer_ficha()
    propia = postulacion(ficha, con_perfil(ana))

    html = ver_ficha(client, ficha, ana)

    assert "Tu postulación para adoptar" in html
    assert reverse("transito:retirar_postulacion", args=[propia.pk]) in html
    assert BOTON not in html


def test_si_ya_la_eligieron_no_puede_retirarla(client, ana):
    ficha = hacer_ficha()
    propia = postulacion(ficha, con_perfil(ana))
    propia.estado = Postulacion.Estado.ELEGIDA
    propia.save()

    html = ver_ficha(client, ficha, ana)

    assert "¡Te eligieron para darle un hogar!" in html
    assert reverse("transito:retirar_postulacion", args=[propia.pk]) not in html


def test_con_una_postulacion_de_transito_no_ve_el_boton(client, ana):
    ficha = hacer_ficha()
    postulacion(ficha, con_perfil(ana), Postulacion.Tipo.TRANSITO)

    html = ver_ficha(client, ficha, ana)

    assert BOTON not in html
    assert "Tu postulación para adoptar" not in html


def test_al_volver_de_postularse_agradece(client, ana):
    ficha = hacer_ficha()
    postulacion(ficha, con_perfil(ana))

    assert "¡Gracias! Ya enviamos tu postulación." in ver_ficha(
        client, ficha, ana, "?postulado_adopcion=1"
    )


def test_su_postulacion_de_adopcion_no_aparece_en_el_panel_de_transito(client, ana):
    ficha = hacer_ficha()
    postulacion(ficha, con_perfil(ana))

    html = ver_ficha(client, ficha, ana)

    assert "Tu postulación para adoptar" in html
    assert "Tu postulación como hogar de tránsito" not in html
