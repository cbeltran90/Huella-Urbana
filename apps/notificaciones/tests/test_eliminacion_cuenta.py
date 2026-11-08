import pytest

from apps.cuentas.eliminacion import eliminar_cuenta
from apps.notificaciones.models import Notificacion
from apps.notificaciones.servicios import notificar

Tipo = Notificacion.Tipo

pytestmark = pytest.mark.django_db


def test_al_eliminar_la_cuenta_se_borran_sus_notificaciones(ana, beto):
    notificar(ana, Tipo.EVENTO, "Para Ana")
    notificar(beto, Tipo.EVENTO, "Para Beto")

    eliminar_cuenta(ana)

    assert not Notificacion.objects.filter(usuario=ana).exists()
    assert Notificacion.objects.filter(usuario=beto).count() == 1
