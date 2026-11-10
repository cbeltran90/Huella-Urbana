from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import EstadoCuenta, Sancion, Usuario
from apps.fichas.models import FichaAnimal
from apps.transito import postulaciones, servicios
from apps.transito.models import PerfilTransito, Postulacion

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"

pytestmark = pytest.mark.django_db


def crear_hogar(nombre="lucia", **perfil):
    usuario = Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    datos = {
        "especies_aceptadas": "perro",
        "tamano_maximo": "mediano",
        "duracion_maxima_dias": 30,
        "cupo_declarado": 2,
        **perfil,
    }
    PerfilTransito.objects.create(usuario=usuario, **datos)
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


def url(ficha):
    return reverse("transito:postular", args=[ficha.pk])


@pytest.fixture
def lucia(client):
    usuario = crear_hogar()
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


def test_un_visitante_va_al_ingreso(client):
    respuesta = client.get(url(crear_ficha()))
    assert respuesta.status_code == 302
    assert "/cuentas/ingresar/" in respuesta.url


def test_una_cuenta_suspendida_ve_la_pagina_de_suspension(client, lucia):
    Sancion.objects.create(
        usuario=lucia,
        email_hash=lucia.email_hash,
        tipo=Sancion.Tipo.TEMPORAL,
        motivo="Motivo de prueba",
        fin=timezone.now() + timedelta(days=3),
    )
    respuesta = client.get(url(crear_ficha()))
    assert respuesta.status_code == 403
    assert "Tu cuenta está suspendida" in respuesta.content.decode()


def test_la_ficha_inexistente_da_404(client, lucia):
    assert client.get(reverse("transito:postular", args=[999999])).status_code == 404


def test_una_ficha_privada_ajena_da_404(client, lucia):
    assert client.get(url(crear_ficha(es_privada=True))).status_code == 404


def test_el_hogar_ve_el_formulario_con_el_animal(client, lucia):
    respuesta = client.get(url(crear_ficha()))
    contenido = respuesta.content.decode()
    assert respuesta.status_code == 200
    assert "Bruno" in contenido
    assert 'name="contacto"' in contenido
    assert "Enviar postulación" in contenido
    assert "Podés postularte igual" not in contenido


def test_un_hogar_no_compatible_ve_la_advertencia_y_puede_postularse(client, lucia):
    ficha = crear_ficha(tamano="grande")
    respuesta = client.get(url(ficha))
    contenido = respuesta.content.decode()
    assert servicios.MOTIVO_TAMANO in contenido
    assert "Podés postularte igual" in contenido
    assert "Enviar postulación" in contenido


def test_al_enviar_se_crea_la_postulacion_y_vuelve_a_la_ficha(client, lucia):
    ficha = crear_ficha()

    respuesta = client.post(url(ficha), {"contacto": "2901-555555"})

    assert respuesta.status_code == 302
    assert respuesta.url == f"{reverse('fichas:detalle', args=[ficha.pk])}?postulado=1"
    postulacion = Postulacion.objects.get()
    assert postulacion.usuario == lucia
    assert postulacion.ficha == ficha
    assert postulacion.contacto == "2901-555555"
    assert postulacion.estado == Postulacion.Estado.PENDIENTE


def test_sin_canal_de_contacto_se_muestra_el_error_y_no_se_crea_nada(client, lucia):
    respuesta = client.post(url(crear_ficha()), {"contacto": "   "})
    assert respuesta.status_code == 200
    assert postulaciones.MENSAJE_CONTACTO_VACIO in respuesta.content.decode()
    assert not Postulacion.objects.exists()


def test_un_canal_demasiado_largo_se_informa(client, lucia):
    largo = "x" * (postulaciones.CONTACTO_MAXIMO + 1)
    respuesta = client.post(url(crear_ficha()), {"contacto": largo})
    assert postulaciones.MENSAJE_CONTACTO_LARGO in respuesta.content.decode()
    assert not Postulacion.objects.exists()


def test_sin_perfil_de_transito_se_explica_y_se_ofrece_completarlo(client):
    usuario = Usuario.objects.create_user(
        "sin@example.com", "Sin", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND_MODELO)

    respuesta = client.get(url(crear_ficha()))

    contenido = respuesta.content.decode()
    assert postulaciones.MENSAJE_SIN_PERFIL in contenido
    assert reverse("transito:perfil_transito") in contenido
    assert 'name="contacto"' not in contenido


def test_en_pausa_se_informa_y_no_se_ofrece_el_formulario(client, lucia):
    hasta = timezone.localdate() + timedelta(days=10)
    PerfilTransito.objects.filter(usuario=lucia).update(disponibilidad=False, pausa_hasta=hasta)

    respuesta = client.get(url(crear_ficha()))

    contenido = respuesta.content.decode()
    assert postulaciones.MENSAJE_EN_PAUSA in contenido
    assert 'name="contacto"' not in contenido


def test_si_la_ficha_ya_no_esta_en_adopcion_no_se_puede_enviar(client, lucia):
    ficha = crear_ficha(estado=FichaAnimal.Estado.EN_TRANSITO)

    respuesta = client.post(url(ficha), {"contacto": "2901-555555"})

    assert postulaciones.MENSAJE_NO_EN_ADOPCION in respuesta.content.decode()
    assert not Postulacion.objects.exists()


def test_con_una_postulacion_activa_no_se_puede_enviar_otra(client, lucia):
    ficha = crear_ficha()
    postulaciones.postular_transito(lucia, ficha, "2901-111111")

    respuesta = client.post(url(ficha), {"contacto": "2901-222222"})

    assert postulaciones.MENSAJE_YA_POSTULADO in respuesta.content.decode()
    assert ficha.postulaciones.count() == 1


def test_el_animal_a_cargo_del_hogar_no_se_puede_postular(client, lucia):
    ficha = crear_ficha(cuidador=lucia)
    respuesta = client.post(url(ficha), {"contacto": "2901-555555"})
    assert postulaciones.MENSAJE_TIENE_EL_ANIMAL in respuesta.content.decode()
    assert not Postulacion.objects.exists()


def test_el_formulario_lleva_a_la_ficha_para_cancelar(client, lucia):
    ficha = crear_ficha()
    respuesta = client.get(url(ficha))
    assert reverse("fichas:detalle", args=[ficha.pk]) in respuesta.content.decode()
