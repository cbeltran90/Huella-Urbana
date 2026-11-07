import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse

from apps.cuentas.models import Domicilio, EstadoCuenta, Usuario
from apps.transito import servicios
from apps.transito.models import PerfilTransito

CLAVE = "clave-de-prueba-1"
BACKEND = "django.contrib.auth.backends.ModelBackend"


def url():
    return reverse("transito:perfil_transito")


@pytest.fixture
def ana(client):
    usuario = Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND)
    return usuario


def dar_domicilio(usuario, **hogar):
    # Por defecto, una casa con patio: estimado 5.
    datos = {
        "tipo_vivienda": "casa",
        "tiene_patio": True,
        "convivientes": 2,
        "hay_ninos": False,
        "mascotas_propias": 1,
        **hogar,
    }
    return Domicilio.objects.create(
        usuario=usuario,
        ubicacion=Point(-68.30, -54.80, srid=4326),
        ubicacion_desplazada=Point(-68.301, -54.801, srid=4326),
        **datos,
    )


def datos_servicio(**cambios):
    base = {
        "especies": ["perro"],
        "tamano_maximo": "mediano",
        "duracion_maxima_dias": 30,
        "disponibilidad": True,
        "cupo_declarado": 2,
    }
    return {**base, **cambios}


def datos_post(**cambios):
    base = {
        "especies": ["perro"],
        "tamano_maximo": "mediano",
        "duracion_maxima_dias": "30",
        "disponibilidad": "True",
        "cupo_declarado": "2",
    }
    return {**base, **cambios}


# Servicio


@pytest.mark.django_db
def test_un_cupo_igual_al_estimado_se_guarda_sin_aviso(ana):
    dar_domicilio(ana)

    perfil = servicios.guardar_perfil_transito(ana, **datos_servicio(cupo_declarado=5))

    assert perfil.cupo_declarado == 5


@pytest.mark.django_db
def test_un_cupo_mayor_al_estimado_avisa_y_no_guarda(ana):
    dar_domicilio(ana)

    with pytest.raises(servicios.CupoSuperaEstimado) as error:
        servicios.guardar_perfil_transito(ana, **datos_servicio(cupo_declarado=6))

    assert error.value.estimado == 5
    assert str(error.value) == "Podría exceder la capacidad de su vivienda"
    assert not PerfilTransito.objects.exists()


@pytest.mark.django_db
def test_confirmando_el_exceso_se_guarda_el_cupo_elegido(ana):
    dar_domicilio(ana)

    perfil = servicios.guardar_perfil_transito(
        ana, **datos_servicio(cupo_declarado=6), confirmar_exceso=True
    )

    assert perfil.cupo_declarado == 6
    assert servicios.es_hogar_de_transito(ana) is True


@pytest.mark.django_db
def test_con_un_departamento_sin_patio_el_estimado_es_1(ana):
    dar_domicilio(ana, tipo_vivienda="departamento", tiene_patio=False)

    servicios.guardar_perfil_transito(ana, **datos_servicio(cupo_declarado=1))
    with pytest.raises(servicios.CupoSuperaEstimado) as error:
        servicios.guardar_perfil_transito(ana, **datos_servicio(cupo_declarado=2))

    assert error.value.estimado == 1


@pytest.mark.django_db
def test_los_errores_de_validacion_van_antes_que_la_sugerencia(ana):
    dar_domicilio(ana)

    with pytest.raises(servicios.PerfilTransitoInvalido):
        servicios.guardar_perfil_transito(
            ana, **datos_servicio(cupo_declarado=6, duracion_maxima_dias=6)
        )


@pytest.mark.django_db
def test_un_cupo_fuera_de_rango_es_un_error_y_no_una_sugerencia(ana):
    dar_domicilio(ana)

    with pytest.raises(servicios.PerfilTransitoInvalido):
        servicios.guardar_perfil_transito(ana, **datos_servicio(cupo_declarado=21))


@pytest.mark.django_db
def test_si_cambia_la_vivienda_el_estimado_se_recalcula_y_el_cupo_declarado_no(ana):
    dar_domicilio(ana)
    servicios.guardar_perfil_transito(ana, **datos_servicio(cupo_declarado=4))

    Domicilio.objects.filter(usuario=ana).update(tipo_vivienda="departamento", tiene_patio=False)

    domicilio = Domicilio.objects.get(usuario=ana)
    assert servicios.cupo_estimado(domicilio) == 1
    assert PerfilTransito.objects.get(usuario=ana).cupo_declarado == 4


# Pantalla


@pytest.mark.django_db
def test_la_pantalla_muestra_la_capacidad_estimada_como_sugerencia(client, ana):
    dar_domicilio(ana)

    contenido = client.get(url()).content.decode()

    assert "Capacidad estimada de tu vivienda" in contenido
    assert "<strong>5</strong>" in contenido
    assert "solo una sugerencia" in contenido


@pytest.mark.django_db
def test_en_un_perfil_nuevo_el_cupo_arranca_con_el_estimado(client, ana):
    dar_domicilio(ana, tipo_vivienda="departamento", tiene_patio=True)

    contenido = client.get(url()).content.decode()

    assert 'name="cupo_declarado"' in contenido
    assert 'value="3"' in contenido


@pytest.mark.django_db
def test_en_un_perfil_existente_se_respeta_el_cupo_declarado(client, ana):
    dar_domicilio(ana)
    servicios.guardar_perfil_transito(ana, **datos_servicio(cupo_declarado=4))

    contenido = client.get(url()).content.decode()

    assert 'value="4"' in contenido
    assert "<strong>5</strong>" in contenido


@pytest.mark.django_db
def test_sin_datos_del_hogar_no_hay_capacidad_estimada(client, ana):
    contenido = client.get(url()).content.decode()

    assert "Capacidad estimada" not in contenido


@pytest.mark.django_db
def test_un_cupo_mayor_al_estimado_muestra_la_sugerencia_y_pide_confirmar(client, ana):
    dar_domicilio(ana)

    respuesta = client.post(url(), datos_post(cupo_declarado="6"))

    contenido = respuesta.content.decode()
    assert respuesta.status_code == 200
    assert "Podría exceder la capacidad de su vivienda" in contenido
    assert "Confirmar igualmente" in contenido
    assert 'value="6"' in contenido
    assert not PerfilTransito.objects.exists()


@pytest.mark.django_db
def test_confirmar_igualmente_guarda_el_cupo_elegido(client, ana):
    dar_domicilio(ana)

    respuesta = client.post(url(), datos_post(cupo_declarado="6", confirmar_exceso="1"))

    assert respuesta.status_code == 302
    assert respuesta["Location"] == f"{reverse('cuentas:perfil')}?guardado=1"
    assert PerfilTransito.objects.get(usuario=ana).cupo_declarado == 6


@pytest.mark.django_db
def test_un_cupo_dentro_del_estimado_no_muestra_ninguna_sugerencia(client, ana):
    dar_domicilio(ana)

    respuesta = client.post(url(), datos_post(cupo_declarado="5"))

    assert respuesta.status_code == 302
    assert PerfilTransito.objects.get(usuario=ana).cupo_declarado == 5


@pytest.mark.django_db
def test_sin_exceso_no_se_ofrece_confirmar(client, ana):
    dar_domicilio(ana)

    contenido = client.get(url()).content.decode()

    assert "Confirmar igualmente" not in contenido
    assert "Podría exceder" not in contenido
