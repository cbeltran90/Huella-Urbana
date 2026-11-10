from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import EstadoCuenta, Sancion, Usuario
from apps.fichas.models import FichaAnimal
from apps.transito import postulaciones
from apps.transito.models import PerfilTransito, Postulacion

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"
BOTON = "Postularme como hogar de tránsito"
Estado = Postulacion.Estado

pytestmark = pytest.mark.django_db


def crear_hogar(nombre="lucia"):
    usuario = Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    PerfilTransito.objects.create(
        usuario=usuario,
        especies_aceptadas="perro",
        tamano_maximo="mediano",
        duracion_maxima_dias=30,
        cupo_declarado=2,
    )
    return usuario


def crear_ficha(**campos):
    datos = {
        "nombre": "Bruno",
        "especie": "perro",
        "tamano": "mediano",
        "estado": FichaAnimal.Estado.EN_ADOPCION,
        "es_privada": False,
        **campos,
    }
    return FichaAnimal.objects.create(**datos)


def ver(client, ficha, consulta=""):
    return client.get(reverse("fichas:detalle", args=[ficha.pk]) + consulta).content.decode()


@pytest.fixture
def lucia(client):
    usuario = crear_hogar()
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


def test_un_visitante_no_ve_nada_de_postulacion(client):
    contenido = ver(client, crear_ficha())
    assert BOTON not in contenido
    assert "postulación" not in contenido


def test_quien_no_es_hogar_de_transito_no_ve_nada(client):
    usuario = Usuario.objects.create_user(
        "sin@example.com", "Sin", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND_MODELO)
    contenido = ver(client, crear_ficha())
    assert BOTON not in contenido
    assert "postulación" not in contenido


def test_el_hogar_ve_el_boton_que_lleva_a_la_pantalla(client, lucia):
    ficha = crear_ficha()
    contenido = ver(client, ficha)
    assert BOTON in contenido
    assert reverse("transito:postular", args=[ficha.pk]) in contenido


@pytest.mark.parametrize(
    "estado",
    [
        FichaAnimal.Estado.REGISTRADO,
        FichaAnimal.Estado.SIN_RESPONSABLE,
        FichaAnimal.Estado.EN_TRANSITO,
    ],
)
def test_en_una_ficha_que_no_esta_en_adopcion_no_se_ofrece(client, lucia, estado):
    assert BOTON not in ver(client, crear_ficha(estado=estado))


def test_quien_tiene_el_animal_a_su_cargo_no_ve_el_boton(client, lucia):
    assert BOTON not in ver(client, crear_ficha(cuidador=lucia))


def test_en_pausa_se_informa_con_el_enlace_a_su_hogar(client, lucia):
    hasta = timezone.localdate() + timedelta(days=10)
    PerfilTransito.objects.filter(usuario=lucia).update(disponibilidad=False, pausa_hasta=hasta)

    contenido = ver(client, crear_ficha())

    assert BOTON not in contenido
    assert postulaciones.MENSAJE_EN_PAUSA in contenido
    assert reverse("transito:perfil_transito") in contenido


def test_con_la_cuenta_suspendida_se_informa_el_motivo(client, lucia):
    Sancion.objects.create(
        usuario=lucia,
        email_hash=lucia.email_hash,
        tipo=Sancion.Tipo.TEMPORAL,
        motivo="Motivo de prueba",
        fin=timezone.now() + timedelta(days=3),
    )

    contenido = ver(client, crear_ficha())

    assert BOTON not in contenido
    assert postulaciones.MENSAJE_SUSPENDIDO in contenido


def test_con_una_postulacion_pendiente_se_ve_su_estado_y_se_puede_retirar(client, lucia):
    ficha = crear_ficha()
    postulacion = postulaciones.postular_transito(lucia, ficha, "2901-555555")

    contenido = ver(client, ficha)

    assert "Tu postulación como hogar de tránsito" in contenido
    assert "Está pendiente" in contenido
    assert "2901-555555" in contenido
    assert BOTON not in contenido
    assert reverse("transito:retirar_postulacion", args=[postulacion.pk]) in contenido
    assert "csrfmiddlewaretoken" in contenido


def test_con_una_postulacion_elegida_no_se_puede_retirar(client, lucia):
    ficha = crear_ficha()
    postulacion = postulaciones.postular_transito(lucia, ficha, "2901-555555")
    Postulacion.objects.filter(pk=postulacion.pk).update(estado=Estado.ELEGIDA)

    contenido = ver(client, ficha)

    assert "Te eligieron como hogar de tránsito" in contenido
    assert "Retirar postulación" not in contenido


def test_con_una_postulacion_descartada_se_ofrece_postularse_de_nuevo(client, lucia):
    ficha = crear_ficha()
    postulacion = postulaciones.postular_transito(lucia, ficha, "2901-555555")
    Postulacion.objects.filter(pk=postulacion.pk).update(estado=Estado.DESCARTADA)

    contenido = ver(client, ficha)

    assert BOTON in contenido
    assert "Tu postulación como hogar de tránsito" not in contenido


def test_el_aviso_de_postulacion_enviada(client, lucia):
    ficha = crear_ficha()
    postulaciones.postular_transito(lucia, ficha, "2901-555555")
    assert "Enviamos tu postulación" in ver(client, ficha, "?postulado=1")
    assert "Enviamos tu postulación" not in ver(client, ficha)


def test_el_aviso_de_postulacion_retirada(client, lucia):
    ficha = crear_ficha()
    assert "Retiraste tu postulación" in ver(client, ficha, "?retirada=1")
    assert "Retiraste tu postulación" not in ver(client, ficha)


def test_recorrido_postularse_y_retirar_desde_la_ficha(client, lucia):
    ficha = crear_ficha()
    ficha_url = reverse("fichas:detalle", args=[ficha.pk])

    respuesta = client.post(
        reverse("transito:postular", args=[ficha.pk]), {"contacto": "2901-555555"}, follow=True
    )
    contenido = respuesta.content.decode()
    assert "Enviamos tu postulación" in contenido
    assert "Está pendiente" in contenido

    postulacion = Postulacion.objects.get()
    respuesta = client.post(
        reverse("transito:retirar_postulacion", args=[postulacion.pk]), follow=True
    )
    contenido = respuesta.content.decode()
    assert respuesta.redirect_chain[-1][0] == f"{ficha_url}?retirada=1"
    assert "Retiraste tu postulación" in contenido
    assert BOTON in contenido
