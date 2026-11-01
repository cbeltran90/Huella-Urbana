import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse

from apps.cuentas.models import EstadoCuenta, Rol, Usuario, hash_email

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"


def crear_usuario(email="ana@example.com", nombre="Ana", **extra):
    return Usuario.objects.create_user(email, nombre, CLAVE, **extra)


def crear_admin(email="admin@example.com"):
    return Usuario.objects.create_superuser(email, "Admin", CLAVE)


@pytest.mark.django_db
def test_usuario_nuevo_queda_pendiente_e_inactivo():
    usuario = crear_usuario()
    assert usuario.check_password(CLAVE)
    assert usuario.estado_cuenta == EstadoCuenta.PENDIENTE
    assert usuario.rol == Rol.REGISTRADO
    assert not usuario.is_active
    assert not usuario.is_staff


@pytest.mark.django_db
def test_el_correo_se_normaliza_y_se_calcula_el_hash():
    usuario = crear_usuario(email="  Ana@Example.COM ")
    assert usuario.email == "ana@example.com"
    assert usuario.email_hash == hash_email("ana@example.com")
    assert len(usuario.email_hash) == 64


@pytest.mark.django_db
def test_el_correo_y_el_nombre_son_obligatorios():
    with pytest.raises(ValueError):
        Usuario.objects.create_user("", "Ana", CLAVE)
    with pytest.raises(ValueError):
        Usuario.objects.create_user("ana@example.com", "", CLAVE)


@pytest.mark.django_db
def test_superusuario_queda_activo_y_administrador():
    admin = crear_admin()
    assert admin.is_active
    assert admin.is_staff
    assert admin.is_superuser
    assert admin.rol == Rol.ADMINISTRADOR
    assert admin.estado_cuenta == EstadoCuenta.ACTIVA


@pytest.mark.django_db
def test_activar_la_cuenta_activa_is_active():
    usuario = crear_usuario()
    usuario.estado_cuenta = EstadoCuenta.ACTIVA
    usuario.save()
    usuario.refresh_from_db()
    assert usuario.is_active


@pytest.mark.django_db
def test_guardar_solo_el_estado_tambien_guarda_is_active():
    usuario = crear_usuario()
    usuario.estado_cuenta = EstadoCuenta.ACTIVA
    usuario.save(update_fields=["estado_cuenta"])
    usuario.refresh_from_db()
    assert usuario.is_active
    usuario.estado_cuenta = EstadoCuenta.ELIMINADA
    usuario.save(update_fields=["estado_cuenta"])
    usuario.refresh_from_db()
    assert not usuario.is_active


@pytest.mark.django_db
def test_correo_repetido_con_otras_mayusculas_se_rechaza():
    crear_usuario()
    with pytest.raises(IntegrityError):
        crear_usuario(email="ANA@example.com", nombre="Otra")


@pytest.mark.django_db
def test_nombre_repetido_sin_distinguir_mayusculas_se_rechaza():
    crear_usuario()
    with pytest.raises(IntegrityError):
        crear_usuario(email="otra@example.com", nombre="ANA")


@pytest.mark.django_db
def test_nombre_repetido_da_el_mensaje_del_caso_de_uso():
    crear_usuario()
    repetido = Usuario(email="otra@example.com", nombre_usuario="ana")
    with pytest.raises(ValidationError) as error:
        repetido.full_clean(exclude=["password"])
    assert "Nombre ya usado" in str(error.value)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "nombre_url",
    ["admin:cuentas_usuario_changelist", "admin:cuentas_usuario_add"],
)
def test_el_admin_de_usuarios_carga(client, nombre_url):
    client.force_login(crear_admin(), backend=BACKEND_MODELO)
    assert client.get(reverse(nombre_url)).status_code == 200


@pytest.mark.django_db
def test_el_admin_muestra_la_ficha_de_un_usuario(client):
    admin = crear_admin()
    client.force_login(admin, backend=BACKEND_MODELO)
    url = reverse("admin:cuentas_usuario_change", args=[admin.pk])
    assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_el_admin_acepta_el_correo_como_usuario(client):
    crear_admin()
    datos = {"username": "Admin@Example.com", "password": CLAVE}
    respuesta = client.post(reverse("admin:login"), datos)
    assert respuesta.status_code == 302


@pytest.mark.django_db
def test_una_cuenta_pendiente_no_puede_entrar(client):
    crear_usuario(is_staff=True)
    datos = {"username": "ana@example.com", "password": CLAVE}
    respuesta = client.post(reverse("admin:login"), datos)
    assert respuesta.status_code == 200


@pytest.mark.django_db
def test_axes_bloquea_tras_cinco_intentos_fallidos_con_el_correo(client):
    crear_admin()
    url = reverse("admin:login")
    datos = {"username": "admin@example.com", "password": "incorrecta-123"}
    codigos = [client.post(url, datos).status_code for _ in range(7)]
    assert codigos[:4] == [200, 200, 200, 200]
    assert set(codigos[5:]) == {429}
