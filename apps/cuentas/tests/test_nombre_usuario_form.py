import pytest
from django.core.exceptions import ValidationError

from apps.cuentas.forms import (
    MENSAJE_NOMBRE_OFENSIVO,
    MENSAJE_NOMBRE_USADO,
    NombreUsuarioForm,
)
from apps.cuentas.models import EstadoCuenta, Usuario

CLAVE = "clave-de-prueba-1"


@pytest.fixture
def ana(db):
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def formulario(ana, nombre):
    return NombreUsuarioForm({"nombre_usuario": nombre}, usuario=ana)


def test_se_cambia_el_nombre(ana):
    form = formulario(ana, "Ana Sol")
    assert form.is_valid()
    form.save()
    ana.refresh_from_db()
    assert ana.nombre_usuario == "Ana Sol"


def test_se_pueden_cambiar_las_mayusculas_del_propio_nombre(ana):
    form = formulario(ana, "ANA")
    assert form.is_valid()
    form.save()
    ana.refresh_from_db()
    assert ana.nombre_usuario == "ANA"


def test_un_nombre_de_otra_persona_se_rechaza_sin_importar_mayusculas(ana):
    Usuario.objects.create_user(
        "beto@example.com", "Beto", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    form = formulario(ana, "bETO")
    assert not form.is_valid()
    assert form.errors["nombre_usuario"] == [MENSAJE_NOMBRE_USADO]


def test_un_nombre_ofensivo_se_rechaza_y_no_se_guarda(ana):
    form = formulario(ana, "Puto")
    assert not form.is_valid()
    assert MENSAJE_NOMBRE_OFENSIVO in form.errors["nombre_usuario"]
    ana.refresh_from_db()
    assert ana.nombre_usuario == "Ana"


def test_un_nombre_vacio_se_rechaza(ana):
    assert not formulario(ana, "   ").is_valid()


def test_un_nombre_demasiado_largo_se_rechaza(ana):
    assert not formulario(ana, "a" * 151).is_valid()


def test_si_otra_persona_toma_el_nombre_justo_antes_de_guardar_se_rechaza(ana):
    form = formulario(ana, "Beto")
    assert form.is_valid()
    Usuario.objects.create_user(
        "beto@example.com", "beto", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )

    with pytest.raises(ValidationError):
        form.save()

    ana.refresh_from_db()
    assert ana.nombre_usuario == "Ana"
