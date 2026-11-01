import pytest

from apps.cuentas import servicios
from apps.cuentas.forms import RegistroForm
from apps.cuentas.models import EstadoCuenta, Rol, Usuario

CLAVE = "clave-de-prueba-1"


def datos(**cambios):
    base = {
        "nombre_usuario": "Ana",
        "email": "ana@example.com",
        "password1": CLAVE,
        "password2": CLAVE,
        "acepta_condiciones": "on",
    }
    return {**base, **cambios}


@pytest.mark.django_db
def test_registro_valido_crea_una_cuenta_pendiente():
    form = RegistroForm(datos())
    assert form.is_valid(), form.errors
    usuario = form.save()
    assert usuario.email == "ana@example.com"
    assert usuario.estado_cuenta == EstadoCuenta.PENDIENTE
    assert usuario.rol == Rol.REGISTRADO
    assert not usuario.is_active
    assert usuario.acepto_condiciones_at is not None
    assert usuario.check_password(CLAVE)


@pytest.mark.django_db
def test_el_correo_se_guarda_normalizado():
    form = RegistroForm(datos(email="  Ana@Example.COM "))
    assert form.is_valid(), form.errors
    assert form.cleaned_data["email"] == "ana@example.com"


@pytest.mark.django_db
def test_sin_aceptar_las_condiciones_no_se_crea_la_cuenta():
    form = RegistroForm(datos(acepta_condiciones=""))
    assert not form.is_valid()
    mensaje = "Debe aceptar las condiciones de uso y la política de datos"
    assert form.errors["acepta_condiciones"] == [mensaje]
    assert Usuario.objects.count() == 0


@pytest.mark.django_db
def test_contrasena_corta_da_el_mensaje_del_caso_de_uso():
    form = RegistroForm(datos(password1="Zq7mWp3xK", password2="Zq7mWp3xK"))
    assert not form.is_valid()
    mensaje = "La contraseña debe tener al menos 10 caracteres"
    assert form.errors["password1"] == [mensaje]


@pytest.mark.django_db
def test_contrasenas_distintas():
    form = RegistroForm(datos(password2="otra-clave-distinta-2"))
    assert not form.is_valid()
    assert form.errors["password2"] == ["Las contraseñas no coinciden"]


@pytest.mark.django_db
def test_nombre_ofensivo():
    form = RegistroForm(datos(nombre_usuario="PelotudoMax"))
    assert not form.is_valid()
    assert form.errors["nombre_usuario"] == ["Nombre ofensivo"]


@pytest.mark.django_db
def test_nombre_ya_usado_sin_distinguir_mayusculas():
    Usuario.objects.create_user("otra@example.com", "ana", CLAVE)
    form = RegistroForm(datos(nombre_usuario="ANA"))
    assert not form.is_valid()
    assert form.errors["nombre_usuario"] == ["Nombre ya usado"]


@pytest.mark.django_db
def test_correo_ya_registrado_sin_distinguir_mayusculas():
    Usuario.objects.create_user("ana@example.com", "Otra", CLAVE)
    form = RegistroForm(datos(email="ANA@example.com"))
    assert not form.is_valid()
    mensaje = "El correo electrónico ingresado ya se encuentra registrado"
    assert form.errors["email"] == [mensaje]


@pytest.mark.django_db
def test_correo_con_suspension_permanente(monkeypatch):
    monkeypatch.setattr(servicios, "correo_con_suspension_permanente", lambda email: True)
    form = RegistroForm(datos())
    assert not form.is_valid()
    assert form.errors["email"] == ["Correo con suspensión permanente"]
