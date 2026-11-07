import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType

from apps.cuentas.models import EstadoCuenta, Rol, Usuario
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


@pytest.fixture
def administrador():
    return Usuario.objects.create_superuser("root@example.com", "Root", CLAVE)


def crear_perfil(usuario, **campos):
    datos = {
        "especies_aceptadas": "perro",
        "tamano_maximo": "mediano",
        "duracion_maxima_dias": 30,
        "cupo_declarado": 2,
        **campos,
    }
    return PerfilTransito.objects.create(usuario=usuario, **datos)


def registros_de(usuario):
    return LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(Usuario), object_id=str(usuario.pk)
    )


@pytest.mark.django_db
def test_un_moderador_retira_el_rol_y_se_conservan_los_datos(ana, moderadora):
    crear_perfil(ana, cupo_declarado=3)

    perfil = servicios.retirar_rol_transito(ana, moderadora)

    assert perfil.activo is False
    assert servicios.es_hogar_de_transito(ana) is False
    assert PerfilTransito.objects.get(usuario=ana).cupo_declarado == 3


@pytest.mark.django_db
def test_un_administrador_tambien_puede_retirarlo(ana, administrador):
    crear_perfil(ana)

    servicios.retirar_rol_transito(ana, administrador)

    assert servicios.es_hogar_de_transito(ana) is False


@pytest.mark.django_db
def test_el_rol_de_la_cuenta_no_cambia(ana, moderadora):
    crear_perfil(ana)

    servicios.retirar_rol_transito(ana, moderadora)

    ana.refresh_from_db()
    assert ana.rol == Rol.REGISTRADO


@pytest.mark.django_db
def test_queda_registrado_quien_que_y_cuando(ana, moderadora):
    crear_perfil(ana)

    servicios.retirar_rol_transito(ana, moderadora)

    entrada = registros_de(ana).get()
    assert entrada.user == moderadora
    assert entrada.action_flag == CHANGE
    assert entrada.action_time is not None
    assert "hogar de tránsito" in entrada.get_change_message()


@pytest.mark.django_db
def test_con_animales_a_cargo_no_se_retira_y_no_queda_registro(ana, moderadora, monkeypatch):
    crear_perfil(ana)
    monkeypatch.setattr(servicios, "tiene_animales_a_cargo", lambda usuario: True)

    with pytest.raises(servicios.RetiroNoPermitido) as error:
        servicios.retirar_rol_transito(ana, moderadora)

    assert str(error.value) == servicios.MENSAJE_RETIRO_CON_ANIMALES
    assert servicios.es_hogar_de_transito(ana) is True
    assert not registros_de(ana).exists()


@pytest.mark.django_db
def test_una_persona_registrada_no_puede_retirar_el_rol_de_otra(ana):
    beto = Usuario.objects.create_user(
        "beto@example.com", "Beto", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    crear_perfil(ana)

    with pytest.raises(servicios.RetiroNoPermitido) as error:
        servicios.retirar_rol_transito(ana, beto)

    assert str(error.value) == servicios.MENSAJE_RETIRO_SIN_PERMISO
    assert servicios.es_hogar_de_transito(ana) is True
    assert not registros_de(ana).exists()


@pytest.mark.django_db
def test_sin_perfil_activo_no_hay_rol_que_retirar(ana, moderadora):
    with pytest.raises(servicios.SinPerfilActivo):
        servicios.retirar_rol_transito(ana, moderadora)


@pytest.mark.django_db
def test_un_perfil_ya_desactivado_no_se_retira_de_nuevo(ana, moderadora):
    crear_perfil(ana, activo=False)

    with pytest.raises(servicios.SinPerfilActivo):
        servicios.retirar_rol_transito(ana, moderadora)

    assert not registros_de(ana).exists()


def test_el_rol_de_hogar_de_transito_no_se_ofrece_para_asignar():
    # CU-07, 4A: se obtiene al completar el perfil, no se asigna desde la gestión de roles.
    valores = [valor for valor, _ in Rol.choices]

    assert not any("transito" in valor for valor in valores)
