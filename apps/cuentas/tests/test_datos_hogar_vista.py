import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse

from apps.cuentas import servicios
from apps.cuentas.forms import MENSAJE_HOGAR_VIVIENDA
from apps.cuentas.models import CAMPOS_HOGAR, Domicilio, EstadoCuenta, Rol, Sancion, Usuario

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"
EXACTO = Point(-68.3100, -54.8100, srid=4326)
DESPLAZADO = Point(-68.3040, -54.8025, srid=4326)


def url():
    return reverse("cuentas:datos_hogar")


@pytest.fixture
def ana(client):
    usuario = Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


@pytest.fixture
def domicilio(ana):
    return Domicilio.objects.create(usuario=ana, ubicacion=EXACTO, ubicacion_desplazada=DESPLAZADO)


def datos(**cambios):
    base = {
        "tipo_vivienda": "casa",
        "tiene_patio": "True",
        "convivientes": "2",
        "hay_ninos": "False",
        "mascotas_propias": "1",
    }
    return {**base, **cambios}


@pytest.mark.django_db
def test_un_visitante_va_al_ingreso(client):
    respuesta = client.get(url())

    assert respuesta.status_code == 302
    assert reverse("cuentas:login") in respuesta["Location"]


@pytest.mark.django_db
def test_una_cuenta_suspendida_recibe_403_y_no_guarda(client, ana, domicilio):
    moderadora = Usuario.objects.create_user(
        "mod@example.com", "Mod", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, rol=Rol.MODERADOR
    )
    servicios.sancionar(ana, Sancion.Tipo.PERMANENTE, "Motivo", moderadora)

    respuesta = client.post(url(), datos())

    assert respuesta.status_code == 403
    domicilio.refresh_from_db()
    assert not domicilio.hogar_completo


@pytest.mark.django_db
def test_sin_domicilio_pide_registrarlo_primero(client, ana):
    respuesta = client.get(url())

    assert respuesta.status_code == 200
    assert respuesta.context["sin_domicilio"] is True
    assert reverse("cuentas:domicilio") in respuesta.content.decode()


@pytest.mark.django_db
def test_sin_domicilio_no_se_guarda_nada(client, ana):
    respuesta = client.post(url(), datos())

    assert respuesta.status_code == 200
    assert not Domicilio.objects.exists()


@pytest.mark.django_db
def test_la_pantalla_carga_con_el_formulario(client, ana, domicilio):
    respuesta = client.get(url())

    assert respuesta.status_code == 200
    assert "sin_domicilio" not in respuesta.context
    assert respuesta.context["form"].is_bound is False


@pytest.mark.django_db
def test_la_pantalla_muestra_los_datos_ya_guardados(client, ana, domicilio):
    domicilio.tipo_vivienda = "departamento"
    domicilio.tiene_patio = False
    domicilio.convivientes = 3
    domicilio.save()

    form = client.get(url()).context["form"]

    assert form["tipo_vivienda"].value() == "departamento"
    assert form["tiene_patio"].value() is False
    assert form["convivientes"].value() == 3


@pytest.mark.django_db
def test_se_guardan_los_datos_y_vuelve_al_perfil(client, ana, domicilio):
    respuesta = client.post(url(), datos())

    assert respuesta.status_code == 302
    assert respuesta["Location"] == f"{reverse('cuentas:perfil')}?guardado=1"
    domicilio.refresh_from_db()
    assert domicilio.tipo_vivienda == "casa"
    assert domicilio.tiene_patio is True
    assert domicilio.convivientes == 2
    assert domicilio.hay_ninos is False
    assert domicilio.mascotas_propias == 1
    assert domicilio.hogar_completo


@pytest.mark.django_db
def test_un_cero_y_un_no_son_respuestas_validas(client, ana, domicilio):
    respuesta = client.post(
        url(),
        datos(tiene_patio="False", convivientes="0", hay_ninos="False", mascotas_propias="0"),
    )

    assert respuesta.status_code == 302
    domicilio.refresh_from_db()
    assert domicilio.tiene_patio is False
    assert domicilio.convivientes == 0
    assert domicilio.mascotas_propias == 0
    assert domicilio.hogar_completo


@pytest.mark.django_db
@pytest.mark.parametrize("campo", CAMPOS_HOGAR)
def test_si_falta_un_dato_no_se_guarda_nada(client, ana, domicilio, campo):
    enviados = datos()
    del enviados[campo]

    respuesta = client.post(url(), enviados)

    assert respuesta.status_code == 200
    assert campo in respuesta.context["form"].errors
    domicilio.refresh_from_db()
    assert domicilio.hogar_faltante() == list(CAMPOS_HOGAR)


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("tipo_vivienda", "castillo"),
        ("tiene_patio", "quizas"),
        ("hay_ninos", "quizas"),
        ("convivientes", "-1"),
        ("convivientes", "21"),
        ("convivientes", "muchos"),
        ("convivientes", "1.5"),
        ("mascotas_propias", "-1"),
        ("mascotas_propias", "31"),
        ("mascotas_propias", "muchas"),
    ],
)
def test_un_valor_invalido_se_rechaza(client, ana, domicilio, campo, valor):
    respuesta = client.post(url(), datos(**{campo: valor}))

    assert respuesta.status_code == 200
    assert campo in respuesta.context["form"].errors
    domicilio.refresh_from_db()
    assert domicilio.hogar_faltante() == list(CAMPOS_HOGAR)


@pytest.mark.django_db
def test_sin_tipo_de_vivienda_muestra_el_mensaje(client, ana, domicilio):
    respuesta = client.post(url(), datos(tipo_vivienda=""))

    assert MENSAJE_HOGAR_VIVIENDA in respuesta.content.decode()


@pytest.mark.django_db
def test_guardar_el_hogar_no_cambia_el_punto(client, ana, domicilio):
    client.post(url(), datos())

    domicilio.refresh_from_db()
    assert domicilio.ubicacion.equals_exact(EXACTO, 1e-9)
    assert domicilio.ubicacion_desplazada.equals_exact(DESPLAZADO, 1e-9)


@pytest.mark.django_db
def test_cambiar_el_punto_no_borra_los_datos_del_hogar(client, ana, domicilio):
    client.post(url(), datos())

    servicios.guardar_domicilio(ana, Point(-68.3200, -54.8200, srid=4326))

    domicilio.refresh_from_db()
    assert domicilio.ubicacion.equals_exact(Point(-68.3200, -54.8200, srid=4326), 1e-9)
    assert domicilio.hogar_completo


@pytest.mark.django_db
def test_el_perfil_ofrece_completar_los_datos_del_hogar(client, ana, domicilio):
    respuesta = client.get(reverse("cuentas:perfil"))
    contenido = respuesta.content.decode()

    assert "Sin completar" in contenido
    assert url() in contenido


@pytest.mark.django_db
def test_el_perfil_muestra_los_datos_del_hogar(client, ana, domicilio):
    client.post(url(), datos())

    contenido = client.get(reverse("cuentas:perfil")).content.decode()

    assert "Casa" in contenido
    assert "Sin completar" not in contenido
