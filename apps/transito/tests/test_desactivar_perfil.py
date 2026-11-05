import pytest
from django.urls import reverse

from apps.cuentas.models import EstadoCuenta, Usuario
from apps.transito import servicios
from apps.transito.models import PerfilTransito

CLAVE = "clave-de-prueba-1"
BACKEND = "django.contrib.auth.backends.ModelBackend"


def url():
    return reverse("transito:desactivar_perfil")


@pytest.fixture
def ana(client):
    usuario = Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND)
    return usuario


def crear_perfil(usuario, **campos):
    datos = {
        "especies_aceptadas": "perro",
        "tamano_maximo": "mediano",
        "duracion_maxima_dias": 30,
        "cupo_declarado": 2,
        **campos,
    }
    return PerfilTransito.objects.create(usuario=usuario, **datos)


@pytest.fixture
def con_animales(monkeypatch):
    monkeypatch.setattr(servicios, "tiene_animales_a_cargo", lambda usuario: True)


# Servicio


@pytest.mark.django_db
def test_por_ahora_nadie_tiene_animales_a_cargo(ana):
    assert servicios.tiene_animales_a_cargo(ana) is False


@pytest.mark.django_db
def test_sin_animales_a_cargo_se_desactiva_y_se_conservan_los_datos(ana):
    crear_perfil(ana, cupo_declarado=3)

    servicios.desactivar_perfil_transito(ana)

    perfil = PerfilTransito.objects.get(usuario=ana)
    assert perfil.activo is False
    assert perfil.cupo_declarado == 3
    assert servicios.es_hogar_de_transito(ana) is False


@pytest.mark.django_db
def test_con_animales_a_cargo_no_se_desactiva(ana, con_animales):
    crear_perfil(ana)

    with pytest.raises(servicios.DesactivacionNoPermitida) as error:
        servicios.desactivar_perfil_transito(ana)

    assert str(error.value) == servicios.MENSAJE_ANIMALES_A_CARGO
    assert servicios.es_hogar_de_transito(ana) is True


@pytest.mark.django_db
def test_sin_perfil_no_hay_nada_que_desactivar(ana):
    with pytest.raises(servicios.SinPerfilActivo):
        servicios.desactivar_perfil_transito(ana)


@pytest.mark.django_db
def test_un_perfil_ya_desactivado_no_se_desactiva_de_nuevo(ana):
    crear_perfil(ana, activo=False)

    with pytest.raises(servicios.SinPerfilActivo):
        servicios.desactivar_perfil_transito(ana)


# Pantalla


@pytest.mark.django_db
def test_un_visitante_va_a_iniciar_sesion(client):
    respuesta = client.get(url())

    assert respuesta.status_code == 302
    assert reverse("cuentas:login") in respuesta["Location"]


@pytest.mark.django_db
def test_sin_perfil_activo_vuelve_a_la_pantalla_del_perfil_de_transito(client, ana):
    respuesta = client.get(url())

    assert respuesta.status_code == 302
    assert respuesta["Location"] == reverse("transito:perfil_transito")


@pytest.mark.django_db
def test_pide_confirmacion_antes_de_desactivar(client, ana):
    crear_perfil(ana)

    contenido = client.get(url()).content.decode()

    assert "dejás de ser hogar de tránsito" in contenido
    assert "Desactivar perfil</button>" in contenido
    assert servicios.es_hogar_de_transito(ana) is True


@pytest.mark.django_db
def test_confirmar_desactiva_y_vuelve_al_perfil(client, ana):
    crear_perfil(ana)

    respuesta = client.post(url())

    assert respuesta.status_code == 302
    assert respuesta["Location"] == f"{reverse('cuentas:perfil')}?guardado=1"
    assert servicios.es_hogar_de_transito(ana) is False


@pytest.mark.django_db
def test_con_animales_a_cargo_avisa_y_ofrece_pausar(client, ana, con_animales):
    crear_perfil(ana)

    respuesta = client.post(url())

    contenido = respuesta.content.decode()
    assert respuesta.status_code == 200
    assert "No se puede desactivar el perfil" in contenido
    assert "Pausar mi perfil" in contenido
    assert reverse("transito:perfil_transito") in contenido
    assert servicios.es_hogar_de_transito(ana) is True


@pytest.mark.django_db
def test_con_animales_a_cargo_ni_siquiera_ofrece_el_boton_de_desactivar(client, ana, con_animales):
    crear_perfil(ana)

    contenido = client.get(url()).content.decode()

    assert "No se puede desactivar el perfil" in contenido
    assert "Desactivar perfil</button>" not in contenido


@pytest.mark.django_db
def test_la_pantalla_del_perfil_ofrece_desactivar_solo_si_es_hogar_de_transito(client, ana):
    antes = client.get(reverse("transito:perfil_transito")).content.decode()
    crear_perfil(ana)
    despues = client.get(reverse("transito:perfil_transito")).content.decode()

    assert url() not in antes
    assert url() in despues
