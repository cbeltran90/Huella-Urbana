import pytest

from apps.cuentas.models import EstadoCuenta, Rol, Usuario

CLAVE = "clave-de-prueba-1"


def crear(rol, **campos):
    return Usuario.objects.create_user(
        f"{rol}@example.com", rol, CLAVE, rol=rol, estado_cuenta=EstadoCuenta.ACTIVA, **campos
    )


@pytest.mark.django_db
def test_un_registrado_no_entra_al_panel():
    usuario = crear(Rol.REGISTRADO)
    assert not usuario.is_staff
    assert not usuario.is_superuser


@pytest.mark.django_db
def test_un_moderador_entra_al_panel_sin_permisos_totales():
    usuario = crear(Rol.MODERADOR)
    assert usuario.is_staff
    assert not usuario.is_superuser


@pytest.mark.django_db
def test_un_administrador_entra_al_panel_con_permisos_totales():
    usuario = crear(Rol.ADMINISTRADOR)
    assert usuario.is_staff
    assert usuario.is_superuser


@pytest.mark.django_db
def test_el_superusuario_es_administrador():
    usuario = Usuario.objects.create_superuser("root@example.com", "Root", CLAVE)
    assert usuario.rol == Rol.ADMINISTRADOR
    assert usuario.is_staff
    assert usuario.is_superuser


@pytest.mark.django_db
def test_los_permisos_pedidos_a_mano_no_valen_si_el_rol_no_los_da():
    usuario = crear(Rol.REGISTRADO, is_staff=True, is_superuser=True)
    assert not usuario.is_staff
    assert not usuario.is_superuser


@pytest.mark.django_db
def test_cambiar_el_rol_actualiza_el_acceso():
    usuario = crear(Rol.REGISTRADO)

    usuario.rol = Rol.MODERADOR
    usuario.save()
    assert (usuario.is_staff, usuario.is_superuser) == (True, False)

    usuario.rol = Rol.ADMINISTRADOR
    usuario.save()
    assert (usuario.is_staff, usuario.is_superuser) == (True, True)

    usuario.rol = Rol.REGISTRADO
    usuario.save()
    assert (usuario.is_staff, usuario.is_superuser) == (False, False)


@pytest.mark.django_db
def test_guardar_solo_el_rol_tambien_actualiza_el_acceso():
    usuario = crear(Rol.REGISTRADO)

    usuario.rol = Rol.MODERADOR
    usuario.save(update_fields=["rol"])

    usuario.refresh_from_db()
    assert usuario.is_staff
    assert not usuario.is_superuser
