import pytest
from django.db.models import ProtectedError
from model_bakery import baker

from apps.adopcion.models import Adopcion
from apps.adopcion.servicios import tiene_adopcion_registrada
from apps.cuentas.eliminacion import eliminar_cuenta
from apps.fichas import eliminacion as eliminacion_fichas
from apps.fichas import permisos
from apps.fichas.models import FichaAnimal

pytestmark = pytest.mark.django_db


def test_sin_adopcion_la_ficha_no_cuenta_como_adoptada():
    ficha = baker.make(FichaAnimal, especie="perro")
    assert tiene_adopcion_registrada(ficha) is False


def test_con_adopcion_la_ficha_cuenta_como_adoptada(ana, beto):
    ficha = baker.make(FichaAnimal, especie="perro", responsable=ana)
    Adopcion.objects.create(ficha=ficha, adoptante=ana, entregado_por=beto)

    assert tiene_adopcion_registrada(ficha) is True


def test_fichas_y_permisos_de_b_encuentran_la_adopcion(ana):
    """El import tolerante de B tiene que llegar a esta función, no caer en el except."""
    ficha = baker.make(FichaAnimal, especie="perro", responsable=ana)
    Adopcion.objects.create(ficha=ficha, adoptante=ana)

    assert eliminacion_fichas.tiene_adopcion_registrada(ficha) is True
    assert permisos.tiene_adopcion_registrada(ficha) is True


def test_no_se_puede_borrar_una_ficha_con_adopcion(ana):
    ficha = baker.make(FichaAnimal, especie="perro")
    Adopcion.objects.create(ficha=ficha, adoptante=ana)

    with pytest.raises(ProtectedError):
        ficha.delete()


def test_al_eliminar_la_cuenta_se_conserva_la_ficha_adoptada(ana):
    adoptada = baker.make(FichaAnimal, especie="perro", responsable=ana)
    propia = baker.make(FichaAnimal, especie="gato", responsable=ana)
    Adopcion.objects.create(ficha=adoptada, adoptante=ana)

    eliminar_cuenta(ana)

    assert FichaAnimal.objects.filter(pk=adoptada.pk).exists()
    assert not FichaAnimal.objects.filter(pk=propia.pk).exists()
    assert Adopcion.objects.filter(ficha=adoptada, adoptante=ana).exists()
