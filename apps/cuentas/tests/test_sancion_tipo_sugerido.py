import pytest

from apps.cuentas import servicios
from apps.cuentas.models import EstadoCuenta, Rol, Sancion, Usuario

CLAVE = "clave-de-prueba-1"


@pytest.fixture
def ana(db):
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


@pytest.fixture
def moderadora(db):
    return Usuario.objects.create_user(
        "mod@example.com", "Mod", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, rol=Rol.MODERADOR
    )


@pytest.mark.django_db
def test_sin_sanciones_previas_corresponde_la_temporal(ana):
    assert servicios.tipo_sugerido(ana) == Sancion.Tipo.TEMPORAL


@pytest.mark.django_db
def test_con_una_sancion_previa_corresponde_la_permanente(ana, moderadora):
    servicios.sancionar(ana, Sancion.Tipo.TEMPORAL, "Motivo", moderadora)
    assert servicios.tipo_sugerido(ana) == Sancion.Tipo.PERMANENTE


@pytest.mark.django_db
def test_cambiar_de_correo_no_borra_el_historial(ana, moderadora):
    servicios.sancionar(ana, Sancion.Tipo.TEMPORAL, "Motivo", moderadora)

    ana.email = "ana.nueva@example.com"
    ana.save()

    assert servicios.tipo_sugerido(ana) == Sancion.Tipo.PERMANENTE


@pytest.mark.django_db
def test_una_sancion_levantada_no_cuenta(ana, moderadora):
    sancion = servicios.sancionar(ana, Sancion.Tipo.TEMPORAL, "Motivo", moderadora)
    servicios.levantar_sancion(sancion, moderadora)
    assert servicios.tipo_sugerido(ana) == Sancion.Tipo.TEMPORAL


@pytest.mark.django_db
def test_las_sanciones_de_otra_persona_no_cuentan(ana, moderadora):
    beto = Usuario.objects.create_user(
        "beto@example.com", "Beto", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    servicios.sancionar(beto, Sancion.Tipo.TEMPORAL, "Motivo", moderadora)
    assert servicios.tipo_sugerido(ana) == Sancion.Tipo.TEMPORAL
