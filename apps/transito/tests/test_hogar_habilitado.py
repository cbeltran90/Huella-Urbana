from datetime import timedelta

import pytest
from django.utils import timezone

from apps.cuentas.models import EstadoCuenta, Rol, Sancion, Usuario
from apps.cuentas.servicios import levantar_sancion, sancionar
from apps.transito import servicios
from apps.transito.models import PerfilTransito

CLAVE = "clave-de-prueba-1"


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


@pytest.fixture
def moderadora():
    return Usuario.objects.create_user(
        "mod@example.com", "Mod", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, rol=Rol.MODERADOR
    )


def crear_perfil(usuario, **campos):
    datos = {
        "especies_aceptadas": "perro",
        "tamano_maximo": "mediano",
        "duracion_maxima_dias": 30,
        "cupo_declarado": 2,
        **campos,
    }
    return PerfilTransito.objects.create(usuario=usuario, **datos)


def con_alojados(monkeypatch, cantidad):
    monkeypatch.setattr(servicios, "animales_alojados", lambda usuario: cantidad)


# Animales alojados y cupo libre


@pytest.mark.django_db
def test_por_ahora_nadie_tiene_animales_alojados(ana):
    assert servicios.animales_alojados(ana) == 0
    assert servicios.tiene_animales_a_cargo(ana) is False


@pytest.mark.django_db
def test_con_animales_alojados_tiene_animales_a_cargo(ana, monkeypatch):
    con_alojados(monkeypatch, 1)

    assert servicios.tiene_animales_a_cargo(ana) is True


@pytest.mark.django_db
def test_sin_animales_alojados_el_cupo_libre_es_el_declarado(ana):
    assert servicios.cupo_libre(crear_perfil(ana, cupo_declarado=3)) == 3


@pytest.mark.django_db
def test_el_cupo_libre_descuenta_los_animales_alojados(ana, monkeypatch):
    con_alojados(monkeypatch, 2)

    assert servicios.cupo_libre(crear_perfil(ana, cupo_declarado=3)) == 1


@pytest.mark.django_db
def test_el_cupo_libre_nunca_es_negativo(ana, monkeypatch):
    con_alojados(monkeypatch, 5)

    assert servicios.cupo_libre(crear_perfil(ana, cupo_declarado=3)) == 0


# Hogar habilitado (CU-24 y CU-25: disponible y sin suspensión)


@pytest.mark.django_db
def test_un_perfil_activo_y_disponible_esta_habilitado(ana):
    assert servicios.hogar_habilitado(crear_perfil(ana)) is True


@pytest.mark.django_db
def test_un_perfil_desactivado_no_esta_habilitado(ana):
    assert servicios.hogar_habilitado(crear_perfil(ana, activo=False)) is False


@pytest.mark.django_db
def test_en_pausa_no_esta_habilitado_hasta_la_fecha_de_reanudacion(ana):
    hoy = timezone.localdate()
    perfil = crear_perfil(ana, disponibilidad=False, pausa_hasta=hoy + timedelta(days=3))

    assert servicios.hogar_habilitado(perfil, hoy=hoy) is False
    assert servicios.hogar_habilitado(perfil, hoy=hoy + timedelta(days=3)) is True


@pytest.mark.django_db
def test_el_cupo_completo_no_le_quita_la_habilitacion(ana, monkeypatch):
    perfil = crear_perfil(ana, cupo_declarado=2)
    con_alojados(monkeypatch, 2)

    assert servicios.cupo_libre(perfil) == 0
    assert servicios.hogar_habilitado(perfil) is True


@pytest.mark.django_db
def test_una_cuenta_sin_confirmar_no_esta_habilitada():
    pendiente = Usuario.objects.create_user("pen@example.com", "Pen", CLAVE)
    perfil = crear_perfil(pendiente)

    assert pendiente.estado_cuenta != EstadoCuenta.ACTIVA
    assert servicios.hogar_habilitado(perfil) is False


@pytest.mark.django_db
def test_una_cuenta_suspendida_no_esta_habilitada_y_al_levantarse_vuelve(ana, moderadora):
    perfil = crear_perfil(ana)
    sancion = sancionar(ana, Sancion.Tipo.TEMPORAL, "Motivo", moderadora)

    assert servicios.hogar_habilitado(perfil) is False

    levantar_sancion(sancion, moderadora)

    assert servicios.hogar_habilitado(perfil) is True
