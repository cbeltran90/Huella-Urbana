from datetime import timedelta

import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse
from django.utils import timezone

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


def datos(**cambios):
    base = {
        "especies": ["perro"],
        "tamano_maximo": "mediano",
        "duracion_maxima_dias": "30",
        "disponibilidad": "True",
        "cupo_declarado": "2",
    }
    return {**base, **cambios}


def manana():
    return timezone.localdate() + timedelta(days=1)


@pytest.mark.django_db
def test_un_visitante_va_a_iniciar_sesion(client):
    respuesta = client.get(url())

    assert respuesta.status_code == 302
    assert reverse("cuentas:login") in respuesta["Location"]


@pytest.mark.django_db
def test_sin_domicilio_pide_registrarlo(client, ana):
    contenido = client.get(url()).content.decode()

    assert "Primero registrá tu domicilio" in contenido
    assert reverse("cuentas:domicilio") in contenido


@pytest.mark.django_db
def test_con_el_hogar_a_medias_ofrece_completarlo_y_volver(client, ana):
    dar_domicilio(ana, tiene_patio=None)

    contenido = client.get(url()).content.decode()

    assert "Faltan datos de tu hogar" in contenido
    assert f"{reverse('cuentas:datos_hogar')}?volver=transito" in contenido


@pytest.mark.django_db
def test_con_el_hogar_completo_muestra_el_resumen(client, ana):
    dar_domicilio(ana)

    contenido = client.get(url()).content.decode()

    assert "Convivientes: 2" in contenido
    assert "Cambiar los datos del hogar" in contenido


@pytest.mark.django_db
def test_muestra_todos_los_campos_del_perfil(client, ana):
    contenido = client.get(url()).content.decode()

    for nombre in (
        "especies",
        "tamano_maximo",
        "duracion_maxima_dias",
        "acepta_medicacion",
        "acepta_conducta",
        "disponibilidad",
        "pausa_hasta",
        "cupo_declarado",
    ):
        assert f'name="{nombre}"' in contenido


@pytest.mark.django_db
def test_sin_perfil_avisa_que_todavia_no_es_hogar_de_transito(client, ana):
    contenido = client.get(url()).content.decode()

    assert "Todavía no sos hogar de tránsito" in contenido


@pytest.mark.django_db
def test_guardar_activa_el_perfil_y_vuelve_al_perfil(client, ana):
    dar_domicilio(ana)

    respuesta = client.post(url(), datos(acepta_medicacion="on"))

    assert respuesta.status_code == 302
    assert respuesta["Location"] == f"{reverse('cuentas:perfil')}?guardado=1"
    perfil = PerfilTransito.objects.get(usuario=ana)
    assert perfil.especies == ["perro"]
    assert perfil.duracion_maxima_dias == 30
    assert perfil.cupo_declarado == 2
    assert perfil.acepta_medicacion is True
    assert perfil.acepta_conducta is False
    assert servicios.es_hogar_de_transito(ana) is True


@pytest.mark.django_db
def test_con_perfil_activo_la_pantalla_lo_dice_y_muestra_lo_guardado(client, ana):
    dar_domicilio(ana)
    client.post(url(), datos(duracion_maxima_dias="45", cupo_declarado="4"))

    contenido = client.get(url()).content.decode()

    assert "Tu perfil de tránsito está activo" in contenido
    assert 'value="45"' in contenido
    assert 'value="4"' in contenido


@pytest.mark.django_db
def test_guardar_de_nuevo_actualiza_el_perfil(client, ana):
    dar_domicilio(ana)
    client.post(url(), datos())

    client.post(url(), datos(cupo_declarado="5", especies=["perro", "gato"]))

    assert PerfilTransito.objects.count() == 1
    perfil = PerfilTransito.objects.get()
    assert perfil.cupo_declarado == 5
    assert perfil.especies == ["perro", "gato"]


@pytest.mark.django_db
def test_sin_datos_del_hogar_no_guarda_y_dice_que_falta(client, ana):
    respuesta = client.post(url(), datos())

    assert respuesta.status_code == 200
    contenido = respuesta.content.decode()
    assert "No guardamos el perfil" in contenido
    assert "Domicilio" in respuesta.context["faltantes"]
    assert not PerfilTransito.objects.exists()


@pytest.mark.django_db
def test_sin_campos_obligatorios_no_guarda_y_los_lista(client, ana):
    dar_domicilio(ana)

    respuesta = client.post(url(), {})

    assert respuesta.status_code == 200
    assert respuesta.context["faltantes"] == [
        servicios.ETIQUETA_ESPECIES,
        servicios.ETIQUETA_TAMANO,
        servicios.ETIQUETA_DURACION,
        servicios.ETIQUETA_DISPONIBILIDAD,
        servicios.ETIQUETA_CUPO,
    ]
    assert not PerfilTransito.objects.exists()
    assert servicios.es_hogar_de_transito(ana) is False


@pytest.mark.django_db
def test_la_duracion_menor_a_la_minima_muestra_el_mensaje(client, ana):
    dar_domicilio(ana)

    respuesta = client.post(url(), datos(duracion_maxima_dias="6"))

    assert "La duración mínima es de 7 días" in respuesta.content.decode()
    assert not PerfilTransito.objects.exists()


@pytest.mark.django_db
def test_ante_un_error_conserva_lo_escrito(client, ana):
    dar_domicilio(ana)

    respuesta = client.post(url(), datos(duracion_maxima_dias="6", cupo_declarado="3"))

    contenido = respuesta.content.decode()
    assert 'value="6"' in contenido
    assert 'value="3"' in contenido


@pytest.mark.django_db
def test_un_numero_mal_escrito_pide_corregirlo(client, ana):
    dar_domicilio(ana)

    respuesta = client.post(url(), datos(duracion_maxima_dias="muchos"))

    assert "Indicá la cantidad de días con un número" in respuesta.content.decode()
    assert not PerfilTransito.objects.exists()


@pytest.mark.django_db
def test_en_pausa_sin_fecha_la_pide(client, ana):
    dar_domicilio(ana)

    respuesta = client.post(url(), datos(disponibilidad="False"))

    assert respuesta.context["faltantes"] == [servicios.ETIQUETA_REANUDACION]
    assert not PerfilTransito.objects.exists()


@pytest.mark.django_db
def test_en_pausa_con_fecha_futura_se_guarda(client, ana):
    dar_domicilio(ana)

    client.post(url(), datos(disponibilidad="False", pausa_hasta=manana().isoformat()))

    perfil = PerfilTransito.objects.get()
    assert perfil.disponibilidad is False
    assert perfil.pausa_hasta == manana()


@pytest.mark.django_db
def test_una_fecha_de_reanudacion_pasada_muestra_el_mensaje(client, ana):
    dar_domicilio(ana)
    ayer = (timezone.localdate() - timedelta(days=1)).isoformat()

    respuesta = client.post(url(), datos(disponibilidad="False", pausa_hasta=ayer))

    assert servicios.MENSAJE_PAUSA_PASADA in respuesta.content.decode()
    assert not PerfilTransito.objects.exists()


@pytest.mark.django_db
def test_al_guardar_los_datos_del_hogar_desde_aca_se_vuelve_a_esta_pantalla(client, ana):
    dar_domicilio(ana, tiene_patio=None)

    respuesta = client.post(
        f"{reverse('cuentas:datos_hogar')}?volver=transito",
        {
            "tipo_vivienda": "casa",
            "tiene_patio": "True",
            "convivientes": "2",
            "hay_ninos": "False",
            "mascotas_propias": "1",
        },
    )

    assert respuesta.status_code == 302
    assert respuesta["Location"] == f"{url()}?guardado=1"


@pytest.mark.django_db
def test_los_datos_del_hogar_ofrecen_volver_a_esta_pantalla(client, ana):
    dar_domicilio(ana)

    contenido = client.get(f"{reverse('cuentas:datos_hogar')}?volver=transito").content.decode()

    assert f'href="{url()}"' in contenido


@pytest.mark.django_db
def test_el_aviso_de_guardado_se_muestra(client, ana):
    contenido = client.get(f"{url()}?guardado=1").content.decode()

    assert "Guardamos tus cambios" in contenido
