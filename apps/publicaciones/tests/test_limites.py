from datetime import timedelta

import pytest
from constance.test import override_config
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from apps.core.limites import limite_publicaciones

from .conftest import hacer_publicacion

pytestmark = pytest.mark.django_db


@limite_publicaciones
def vista(request):
    return HttpResponse("ok")


def pedido(metodo, usuario):
    request = getattr(RequestFactory(), metodo)("/")
    request.user = usuario
    return request


@override_config(MAX_PUBLICACIONES_HORA=2)
def test_al_llegar_al_limite_se_responde_403(ana):
    hacer_publicacion(ana)
    hacer_publicacion(ana)

    assert vista(pedido("post", ana)).status_code == 403


@override_config(MAX_PUBLICACIONES_HORA=2)
def test_por_debajo_del_limite_se_deja_pasar(ana):
    hacer_publicacion(ana)

    assert vista(pedido("post", ana)).status_code == 200


@override_config(MAX_PUBLICACIONES_HORA=1)
def test_abrir_el_formulario_no_cuenta(ana):
    hacer_publicacion(ana)

    assert vista(pedido("get", ana)).status_code == 200


@override_config(MAX_PUBLICACIONES_HORA=1)
def test_las_de_hace_mas_de_una_hora_no_cuentan(ana):
    hacer_publicacion(ana, fecha=timezone.now() - timedelta(hours=2))

    assert vista(pedido("post", ana)).status_code == 200


@override_config(MAX_PUBLICACIONES_HORA=1)
def test_las_de_otro_usuario_no_cuentan(ana, beto):
    hacer_publicacion(beto)

    assert vista(pedido("post", ana)).status_code == 200
