import pytest
from model_bakery import baker

from apps.cuentas import eliminacion as eliminacion_cuenta
from apps.fichas import eliminacion
from apps.fichas.models import FichaAnimal
from apps.imagenes.models import Fotografia

pytestmark = pytest.mark.django_db


def _ficha(responsable, **campos):
    return baker.make(
        FichaAnimal, responsable=responsable, estado=FichaAnimal.Estado.REGISTRADO, **campos
    )


def test_se_borran_las_fichas_registradas_de_la_persona_y_no_las_ajenas(ana, beto):
    _ficha(ana)
    _ficha(ana)
    ajena = _ficha(beto)

    eliminacion_cuenta.eliminar_cuenta(ana)

    assert list(FichaAnimal.objects.all()) == [ajena]


def test_se_borran_las_fotografias_de_las_fichas_borradas(ana):
    ficha = _ficha(ana)
    baker.make(Fotografia, ficha=ficha, archivo="no-existe.jpg")

    eliminacion_cuenta.eliminar_cuenta(ana)

    assert not Fotografia.objects.exists()


def test_se_conservan_las_fichas_con_adopcion_registrada(ana, monkeypatch):
    adoptada = _ficha(ana)
    _ficha(ana)
    monkeypatch.setattr(eliminacion, "tiene_adopcion_registrada", lambda f: f.pk == adoptada.pk)

    eliminacion_cuenta.eliminar_cuenta(ana)

    adoptada.refresh_from_db()
    ana.refresh_from_db()
    assert FichaAnimal.objects.count() == 1
    assert adoptada.responsable == ana
    assert ana.estado_cuenta == "eliminada"  # la ficha puede mostrar "usuario eliminado"


def test_se_le_quita_el_contacto_como_cuidadora_de_fichas_ajenas(ana, beto):
    ficha = _ficha(beto, cuidador=ana, cuidador_contacto="2901-555555")

    eliminacion_cuenta.eliminar_cuenta(ana)

    ficha.refresh_from_db()
    assert ficha.cuidador is None and ficha.cuidador_contacto == ""
    assert ficha.responsable == beto
