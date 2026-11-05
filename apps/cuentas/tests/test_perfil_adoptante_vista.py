import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse

from apps.cuentas import servicios
from apps.cuentas.models import (
    MAX_EXPERIENCIA_PREVIA,
    Domicilio,
    EstadoCuenta,
    PerfilAdoptante,
    Rol,
    Sancion,
    Usuario,
)

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"
EXACTO = Point(-68.3100, -54.8100, srid=4326)
DESPLAZADO = Point(-68.3040, -54.8025, srid=4326)
HOGAR = {
    "tipo_vivienda": "casa",
    "tiene_patio": True,
    "convivientes": 2,
    "hay_ninos": False,
    "mascotas_propias": 1,
}
EXPERIENCIA = "Tuve dos perros y un gato durante diez años."


def url():
    return reverse("cuentas:perfil_adoptante")


@pytest.fixture
def ana(client):
    usuario = Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


def domicilio(usuario, **hogar):
    return Domicilio.objects.create(
        usuario=usuario, ubicacion=EXACTO, ubicacion_desplazada=DESPLAZADO, **hogar
    )


@pytest.fixture
def ana_con_hogar(ana):
    domicilio(ana, **HOGAR)
    return ana


@pytest.mark.django_db
def test_un_visitante_va_al_ingreso(client):
    respuesta = client.get(url())

    assert respuesta.status_code == 302
    assert reverse("cuentas:login") in respuesta["Location"]


@pytest.mark.django_db
def test_una_cuenta_suspendida_recibe_403_y_no_guarda(client, ana_con_hogar):
    moderadora = Usuario.objects.create_user(
        "mod@example.com", "Mod", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, rol=Rol.MODERADOR
    )
    servicios.sancionar(ana_con_hogar, Sancion.Tipo.PERMANENTE, "Motivo", moderadora)

    respuesta = client.post(url(), {"experiencia_previa": EXPERIENCIA})

    assert respuesta.status_code == 403
    assert not PerfilAdoptante.objects.exists()


@pytest.mark.django_db
def test_sin_domicilio_pide_registrarlo(client, ana):
    respuesta = client.get(url())

    assert respuesta.status_code == 200
    assert respuesta.context["hogar_completo"] is False
    assert respuesta.context["puede_postularse"] is False
    assert reverse("cuentas:domicilio") in respuesta.content.decode()


@pytest.mark.django_db
def test_con_datos_del_hogar_incompletos_ofrece_completarlos_y_volver(client, ana):
    domicilio(ana)

    respuesta = client.get(url())

    assert respuesta.context["hogar_completo"] is False
    destino = f"{reverse('cuentas:datos_hogar')}?volver=adopcion"
    assert destino in respuesta.content.decode()


@pytest.mark.django_db
def test_con_el_hogar_completo_lo_muestra(client, ana_con_hogar):
    respuesta = client.get(url())

    assert respuesta.context["hogar_completo"] is True
    assert "Casa" in respuesta.content.decode()


@pytest.mark.django_db
def test_la_pantalla_muestra_la_experiencia_ya_guardada(client, ana_con_hogar):
    servicios.guardar_perfil_adoptante(ana_con_hogar, EXPERIENCIA)

    respuesta = client.get(url())

    assert respuesta.context["form"]["experiencia_previa"].value() == EXPERIENCIA
    assert respuesta.context["puede_postularse"] is True


@pytest.mark.django_db
def test_un_perfil_completo_se_guarda_y_vuelve_al_perfil(client, ana_con_hogar):
    respuesta = client.post(url(), {"experiencia_previa": EXPERIENCIA})

    assert respuesta.status_code == 302
    assert respuesta["Location"] == f"{reverse('cuentas:perfil')}?guardado=1"
    assert PerfilAdoptante.objects.get().experiencia_previa == EXPERIENCIA
    assert servicios.puede_postularse_a_adoptar(ana_con_hogar) is True


@pytest.mark.django_db
def test_sin_domicilio_no_se_guarda_y_dice_que_falta(client, ana):
    respuesta = client.post(url(), {"experiencia_previa": EXPERIENCIA})

    assert respuesta.status_code == 200
    assert "Domicilio" in respuesta.context["faltantes"]
    assert "Domicilio" in respuesta.content.decode()
    assert not PerfilAdoptante.objects.exists()


@pytest.mark.django_db
def test_con_un_dato_del_hogar_faltante_no_se_guarda(client, ana):
    domicilio(ana, **{**HOGAR, "hay_ninos": None})

    respuesta = client.post(url(), {"experiencia_previa": EXPERIENCIA})

    assert respuesta.status_code == 200
    assert respuesta.context["faltantes"] == ["Niños en el hogar"]
    assert "Niños en el hogar" in respuesta.content.decode()
    assert not PerfilAdoptante.objects.exists()
    assert servicios.puede_postularse_a_adoptar(ana) is False


@pytest.mark.django_db
@pytest.mark.parametrize("experiencia", ["", "   "])
def test_sin_experiencia_previa_no_se_guarda(client, ana_con_hogar, experiencia):
    respuesta = client.post(url(), {"experiencia_previa": experiencia})

    assert respuesta.status_code == 200
    assert respuesta.context["faltantes"] == [servicios.ETIQUETA_EXPERIENCIA]
    assert not PerfilAdoptante.objects.exists()
    assert servicios.puede_postularse_a_adoptar(ana_con_hogar) is False


@pytest.mark.django_db
def test_si_faltan_el_hogar_y_la_experiencia_se_listan_ambos(client, ana):
    domicilio(ana, **{**HOGAR, "tipo_vivienda": ""})

    respuesta = client.post(url(), {"experiencia_previa": ""})

    assert respuesta.context["faltantes"] == ["Tipo de vivienda", servicios.ETIQUETA_EXPERIENCIA]


@pytest.mark.django_db
def test_una_experiencia_demasiado_larga_se_rechaza(client, ana_con_hogar):
    respuesta = client.post(url(), {"experiencia_previa": "a" * (MAX_EXPERIENCIA_PREVIA + 1)})

    assert respuesta.status_code == 200
    assert "experiencia_previa" in respuesta.context["form"].errors
    assert servicios.MENSAJE_EXPERIENCIA_LARGA in respuesta.content.decode()
    assert not PerfilAdoptante.objects.exists()


@pytest.mark.django_db
def test_un_intento_incompleto_no_pisa_el_perfil_anterior(client, ana_con_hogar):
    servicios.guardar_perfil_adoptante(ana_con_hogar, "Primera versión")

    client.post(url(), {"experiencia_previa": ""})

    assert PerfilAdoptante.objects.get().experiencia_previa == "Primera versión"


@pytest.mark.django_db
def test_los_datos_del_hogar_vuelven_al_perfil_de_adopcion(client, ana):
    domicilio(ana)
    datos = {
        "tipo_vivienda": "casa",
        "tiene_patio": "True",
        "convivientes": "2",
        "hay_ninos": "False",
        "mascotas_propias": "1",
    }

    respuesta = client.post(f"{reverse('cuentas:datos_hogar')}?volver=adopcion", datos)

    assert respuesta.status_code == 302
    assert respuesta["Location"] == f"{reverse('cuentas:perfil_adoptante')}?guardado=1"


@pytest.mark.django_db
def test_los_datos_del_hogar_sin_volver_van_al_perfil(client, ana):
    domicilio(ana)
    datos = {
        "tipo_vivienda": "casa",
        "tiene_patio": "True",
        "convivientes": "2",
        "hay_ninos": "False",
        "mascotas_propias": "1",
    }

    respuesta = client.post(reverse("cuentas:datos_hogar"), datos)

    assert respuesta["Location"] == f"{reverse('cuentas:perfil')}?guardado=1"


@pytest.mark.django_db
def test_el_perfil_ofrece_el_perfil_de_adopcion(client, ana_con_hogar):
    contenido = client.get(reverse("cuentas:perfil")).content.decode()

    assert "Perfil de adopción" in contenido
    assert url() in contenido
    assert "Sin completar" in contenido


@pytest.mark.django_db
def test_el_perfil_muestra_el_perfil_de_adopcion_completo(client, ana_con_hogar):
    servicios.guardar_perfil_adoptante(ana_con_hogar, EXPERIENCIA)

    contenido = client.get(reverse("cuentas:perfil")).content.decode()

    assert "Completo" in contenido
    assert "Sin completar" not in contenido
