import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse

from apps.cuentas import servicios
from apps.cuentas.forms import MENSAJE_NOMBRE_OFENSIVO, MENSAJE_NOMBRE_USADO
from apps.cuentas.models import Domicilio, EstadoCuenta, PerfilAdoptante, Rol, Sancion, Usuario

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"
EXACTO = Point(-68.3100, -54.8100, srid=4326)
DESPLAZADO = Point(-68.3040, -54.8025, srid=4326)


def url_perfil():
    return reverse("cuentas:perfil")


def url_editar():
    return reverse("cuentas:editar_perfil")


@pytest.fixture
def ana(client):
    usuario = Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


def suspender(usuario):
    moderadora = Usuario.objects.create_user(
        "mod@example.com", "Mod", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, rol=Rol.MODERADOR
    )
    servicios.sancionar(usuario, Sancion.Tipo.PERMANENTE, "Motivo", moderadora)


@pytest.mark.django_db
@pytest.mark.parametrize("nombre", ["cuentas:perfil", "cuentas:editar_perfil"])
def test_un_visitante_va_al_ingreso(client, nombre):
    respuesta = client.get(reverse(nombre))
    assert respuesta.status_code == 302
    assert respuesta.url.startswith("/cuentas/ingresar/?next=")


@pytest.mark.django_db
@pytest.mark.parametrize("nombre", ["cuentas:perfil", "cuentas:editar_perfil"])
def test_una_cuenta_suspendida_recibe_403(client, ana, nombre):
    suspender(ana)
    assert client.get(reverse(nombre)).status_code == 403


@pytest.mark.django_db
def test_una_cuenta_suspendida_no_puede_cambiar_el_nombre(client, ana):
    suspender(ana)
    respuesta = client.post(url_editar(), {"nombre_usuario": "Otro"})
    assert respuesta.status_code == 403
    ana.refresh_from_db()
    assert ana.nombre_usuario == "Ana"


@pytest.mark.django_db
def test_el_perfil_muestra_nombre_y_correo(client, ana):
    contenido = client.get(url_perfil()).content.decode()
    assert "Ana" in contenido
    assert "ana@example.com" in contenido


@pytest.mark.django_db
def test_el_perfil_avisa_si_no_hay_domicilio(client, ana):
    contenido = client.get(url_perfil()).content.decode()
    assert "Todavía no lo registraste" in contenido
    assert 'aria-label="Registrar mi domicilio"' in contenido


@pytest.mark.django_db
def test_el_perfil_muestra_que_hay_domicilio_sin_revelar_puntos(client, ana):
    Domicilio.objects.create(usuario=ana, ubicacion=EXACTO, ubicacion_desplazada=DESPLAZADO)

    contenido = client.get(url_perfil()).content.decode()

    assert "Registrado" in contenido
    assert 'aria-label="Editar mi domicilio"' in contenido
    for fragmento in ("54.8100", "68.3100", "54.8025", "68.3040"):
        assert fragmento not in contenido


@pytest.mark.django_db
def test_la_pantalla_de_edicion_muestra_el_nombre_actual(client, ana):
    respuesta = client.get(url_editar())
    assert respuesta.status_code == 200
    assert 'value="Ana"' in respuesta.content.decode()


@pytest.mark.django_db
def test_se_cambia_el_nombre_y_se_avisa(client, ana):
    respuesta = client.post(url_editar(), {"nombre_usuario": "Ana Sol"})

    assert respuesta.status_code == 302
    assert respuesta.url == f"{url_perfil()}?guardado=1"
    ana.refresh_from_db()
    assert ana.nombre_usuario == "Ana Sol"
    contenido = client.get(respuesta.url).content.decode()
    assert "Guardamos tus cambios" in contenido
    assert "Ana Sol" in contenido


@pytest.mark.django_db
def test_un_nombre_ofensivo_se_rechaza(client, ana):
    respuesta = client.post(url_editar(), {"nombre_usuario": "Puto"})
    assert respuesta.status_code == 200
    assert MENSAJE_NOMBRE_OFENSIVO in respuesta.content.decode()
    ana.refresh_from_db()
    assert ana.nombre_usuario == "Ana"


@pytest.mark.django_db
def test_un_nombre_usado_por_otra_persona_se_rechaza(client, ana):
    Usuario.objects.create_user(
        "beto@example.com", "Beto", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    respuesta = client.post(url_editar(), {"nombre_usuario": "beto"})
    assert respuesta.status_code == 200
    assert MENSAJE_NOMBRE_USADO in respuesta.content.decode()
    ana.refresh_from_db()
    assert ana.nombre_usuario == "Ana"


@pytest.mark.django_db
def test_un_nombre_vacio_se_rechaza(client, ana):
    respuesta = client.post(url_editar(), {"nombre_usuario": ""})
    assert respuesta.status_code == 200
    ana.refresh_from_db()
    assert ana.nombre_usuario == "Ana"


@pytest.mark.django_db
def test_cada_dato_tiene_su_enlace_para_editarlo(client, ana):
    contenido = client.get(url_perfil()).content.decode()

    rutas = (
        "editar_perfil",
        "cambiar_correo",
        "domicilio",
        "datos_hogar",
        "perfil_adoptante",
        "cambiar_contrasena",
    )
    for ruta in rutas:
        assert reverse(f"cuentas:{ruta}") in contenido


@pytest.mark.django_db
def test_los_enlaces_piden_registrar_o_completar_lo_que_falta(client, ana):
    contenido = client.get(url_perfil()).content.decode()

    assert 'aria-label="Editar nombre de usuario"' in contenido
    assert 'aria-label="Editar correo electrónico"' in contenido
    assert 'aria-label="Registrar mi domicilio"' in contenido
    assert 'aria-label="Completar los datos del hogar"' in contenido
    assert 'aria-label="Completar el perfil de hogar y familia"' in contenido


@pytest.mark.django_db
def test_los_enlaces_ofrecen_editar_lo_que_ya_esta_cargado(client, ana):
    Domicilio.objects.create(
        usuario=ana,
        ubicacion=EXACTO,
        ubicacion_desplazada=DESPLAZADO,
        tipo_vivienda="casa",
        tiene_patio=True,
        convivientes=2,
        hay_ninos=False,
        mascotas_propias=0,
    )
    PerfilAdoptante.objects.create(usuario=ana, experiencia_previa="Tuve perros")

    contenido = client.get(url_perfil()).content.decode()

    assert 'aria-label="Editar mi domicilio"' in contenido
    assert 'aria-label="Editar los datos del hogar"' in contenido
    assert 'aria-label="Editar el perfil de hogar y familia"' in contenido
    assert "Registrar mi domicilio" not in contenido
    assert "Completar los datos del hogar" not in contenido
    assert "Completar el perfil de hogar y familia" not in contenido
