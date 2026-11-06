import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse

from apps.cuentas.models import Domicilio, EstadoCuenta, Usuario
from apps.transito import servicios
from apps.transito.models import PerfilTransito

CLAVE = "clave-de-prueba-1"
BACKEND = "django.contrib.auth.backends.ModelBackend"


@pytest.fixture
def ana(client):
    usuario = Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND)
    Domicilio.objects.create(
        usuario=usuario,
        ubicacion=Point(-68.30, -54.80, srid=4326),
        ubicacion_desplazada=Point(-68.301, -54.801, srid=4326),
        tipo_vivienda="casa",
        tiene_patio=True,
        convivientes=2,
        hay_ninos=False,
        mascotas_propias=1,
    )
    return usuario


def datos_servicio(**cambios):
    base = {
        "especies": ["perro"],
        "tamano_maximo": "mediano",
        "duracion_maxima_dias": 30,
        "disponibilidad": True,
        "cupo_declarado": 4,
    }
    return {**base, **cambios}


def con_alojados(monkeypatch, cantidad):
    monkeypatch.setattr(servicios, "animales_alojados", lambda usuario: cantidad)


@pytest.mark.django_db
def test_un_cupo_menor_a_los_alojados_no_se_guarda(ana, monkeypatch):
    servicios.guardar_perfil_transito(ana, **datos_servicio(cupo_declarado=4))
    con_alojados(monkeypatch, 3)

    with pytest.raises(servicios.PerfilTransitoInvalido) as error:
        servicios.guardar_perfil_transito(ana, **datos_servicio(cupo_declarado=2))

    assert error.value.errores == {"cupo_declarado": servicios.mensaje_cupo_menor_a_alojados(3)}
    assert PerfilTransito.objects.get(usuario=ana).cupo_declarado == 4


@pytest.mark.django_db
def test_un_cupo_igual_a_los_alojados_se_permite(ana, monkeypatch):
    con_alojados(monkeypatch, 3)

    perfil = servicios.guardar_perfil_transito(ana, **datos_servicio(cupo_declarado=3))

    assert perfil.cupo_declarado == 3


@pytest.mark.django_db
def test_un_cupo_mayor_a_los_alojados_se_permite(ana, monkeypatch):
    con_alojados(monkeypatch, 2)

    perfil = servicios.guardar_perfil_transito(ana, **datos_servicio(cupo_declarado=4))

    assert perfil.cupo_declarado == 4


@pytest.mark.django_db
def test_sin_animales_alojados_cualquier_cupo_valido_se_permite(ana):
    perfil = servicios.guardar_perfil_transito(ana, **datos_servicio(cupo_declarado=1))

    assert perfil.cupo_declarado == 1


@pytest.mark.django_db
def test_si_el_cupo_esta_fuera_de_rango_se_conserva_ese_mensaje(ana, monkeypatch):
    con_alojados(monkeypatch, 2)

    with pytest.raises(servicios.PerfilTransitoInvalido) as error:
        servicios.guardar_perfil_transito(ana, **datos_servicio(cupo_declarado=0))

    assert error.value.errores == {"cupo_declarado": servicios.MENSAJE_CUPO}


@pytest.mark.django_db
def test_esta_regla_va_antes_que_la_sugerencia_del_estimado(ana, monkeypatch):
    con_alojados(monkeypatch, 3)

    # La casa con patio estima 5: con cupo 2 no hay "exceso", pero sí menos que los alojados.
    with pytest.raises(servicios.PerfilTransitoInvalido):
        servicios.guardar_perfil_transito(ana, **datos_servicio(cupo_declarado=2))


@pytest.mark.django_db
def test_la_pantalla_muestra_el_error_con_la_cantidad_de_animales(client, ana, monkeypatch):
    con_alojados(monkeypatch, 2)

    respuesta = client.post(
        reverse("transito:perfil_transito"),
        {
            "especies": ["perro"],
            "tamano_maximo": "mediano",
            "duracion_maxima_dias": "30",
            "disponibilidad": "True",
            "cupo_declarado": "1",
        },
    )

    assert respuesta.status_code == 200
    assert "ya alojás (2)" in respuesta.content.decode()
    assert not PerfilTransito.objects.exists()
