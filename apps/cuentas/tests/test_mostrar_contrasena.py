import pytest
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.cuentas.models import EstadoCuenta, Usuario

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"
BOTON = 'x-data="{ visible: false }"'


@pytest.fixture
def ana(db):
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def comprobar(contenido, campos):
    """Cada campo de contraseña tiene su botón y sigue oculto por defecto."""
    assert contenido.count(BOTON) == len(campos)
    assert contenido.count('type="password"') == len(campos)
    assert "Mostrar contraseña" in contenido
    for campo in campos:
        assert f'name="{campo}"' in contenido
        assert f'id="id_{campo}"' in contenido


@pytest.mark.django_db
def test_ingresar_tiene_el_boton(client):
    contenido = client.get(reverse("cuentas:login")).content.decode()
    comprobar(contenido, ["password"])


@pytest.mark.django_db
def test_crear_cuenta_tiene_el_boton_en_las_dos_contrasenas(client):
    contenido = client.get(reverse("cuentas:registro")).content.decode()
    comprobar(contenido, ["password1", "password2"])


@pytest.mark.django_db
def test_nueva_contrasena_por_recuperacion_tiene_el_boton(client, ana):
    uid = urlsafe_base64_encode(force_bytes(ana.pk))
    token = default_token_generator.make_token(ana)
    url = reverse("cuentas:recuperar_confirmar", args=[uid, token])

    contenido = client.get(url, follow=True).content.decode()

    comprobar(contenido, ["new_password1", "new_password2"])


@pytest.mark.django_db
def test_cambiar_contrasena_tiene_el_boton_en_los_tres_campos(client, ana):
    client.force_login(ana, backend=BACKEND_MODELO)
    contenido = client.get(reverse("cuentas:cambiar_contrasena")).content.decode()
    comprobar(contenido, ["old_password", "new_password1", "new_password2"])
