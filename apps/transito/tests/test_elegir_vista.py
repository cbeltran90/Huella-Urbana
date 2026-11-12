from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import EstadoCuenta, Sancion, Usuario
from apps.fichas.models import FichaAnimal
from apps.notificaciones.models import Notificacion
from apps.transito.models import PerfilTransito, Postulacion

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"

pytestmark = pytest.mark.django_db


def crear_usuario(nombre, **campos):
    return Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, **campos
    )


def crear_hogar(nombre, **perfil):
    usuario = crear_usuario(nombre)
    datos = {
        "especies_aceptadas": "perro",
        "tamano_maximo": "grande",
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


def postular(usuario, ficha, contacto="2901-555555", **campos):
    campos.setdefault("tipo", Postulacion.Tipo.TRANSITO)
    return Postulacion.objects.create(ficha=ficha, usuario=usuario, contacto=contacto, **campos)


def url(ficha):
    return reverse("transito:elegir_hogar", args=[ficha.pk])


def suspender(usuario):
    Sancion.objects.create(
        usuario=usuario,
        email_hash=usuario.email_hash,
        tipo=Sancion.Tipo.TEMPORAL,
        motivo="Motivo de prueba",
        fin=timezone.now() + timedelta(days=3),
    )


@pytest.fixture
def carla(client):
    usuario = crear_usuario("carla")
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


@pytest.fixture
def ficha(carla):
    return crear_ficha(cuidador=carla)


# Acceso


def test_un_visitante_va_al_ingreso(client):
    ficha = crear_ficha(cuidador=crear_usuario("otra"))
    respuesta = client.get(url(ficha))
    assert respuesta.status_code == 302
    assert "/cuentas/ingresar/" in respuesta.url


def test_una_cuenta_suspendida_ve_la_pagina_de_suspension(client, carla, ficha):
    suspender(carla)
    respuesta = client.get(url(ficha))
    assert respuesta.status_code == 403
    assert "Tu cuenta está suspendida" in respuesta.content.decode()


def test_la_ficha_inexistente_da_404(client, carla):
    assert client.get(reverse("transito:elegir_hogar", args=[999999])).status_code == 404


def test_una_ficha_privada_ajena_da_404(client, carla):
    ficha = crear_ficha(cuidador=crear_usuario("otra"), es_privada=True)
    assert client.get(url(ficha)).status_code == 404


def test_un_ajeno_da_403(client, carla):
    ficha = crear_ficha(cuidador=crear_usuario("otra"))
    assert client.get(url(ficha)).status_code == 403


def test_un_hogar_postulante_no_puede_elegir(client):
    hogar = crear_hogar("lucia")
    ficha = crear_ficha(cuidador=crear_usuario("otra"))
    postulacion = postular(hogar, ficha)
    client.force_login(hogar, backend=BACKEND_MODELO)

    assert client.get(url(ficha)).status_code == 403
    assert client.post(url(ficha), {"postulacion": postulacion.pk}).status_code == 403
    postulacion.refresh_from_db()
    assert postulacion.estado == Postulacion.Estado.PENDIENTE


def test_con_otro_estado_da_403(client, carla):
    ficha = crear_ficha(cuidador=carla, estado=FichaAnimal.Estado.EN_TRANSITO)
    assert client.get(url(ficha)).status_code == 403


# Lista


def test_muestra_los_postulantes_con_contacto_y_boton_y_no_cambia_nada(client, ficha):
    postulacion = postular(crear_hogar("lucia"), ficha, contacto="lucia@example.com")

    respuesta = client.get(url(ficha))
    html = respuesta.content.decode()

    assert respuesta.status_code == 200
    assert "Lucia" in html
    assert "lucia@example.com" in html
    assert "Plazas libres: 2" in html
    assert "Elegir este hogar" in html
    postulacion.refresh_from_db()
    assert postulacion.estado == Postulacion.Estado.PENDIENTE
    assert Notificacion.objects.count() == 0


def test_no_muestra_a_los_hogares_en_pausa(client, ficha):
    en_pausa = crear_hogar(
        "pausa", disponibilidad=False, pausa_hasta=timezone.localdate() + timedelta(days=10)
    )
    postular(en_pausa, ficha, contacto="pausa@example.com")

    html = client.get(url(ficha)).content.decode()

    assert "pausa@example.com" not in html
    assert "No hay postulaciones de hogares habilitados" in html


def test_muestra_la_advertencia_de_incompatibilidad(client, carla):
    ficha = crear_ficha(cuidador=carla, especie="gato")
    postular(crear_hogar("lucia"), ficha)

    html = client.get(url(ficha)).content.decode()

    assert "puede no ser compatible" in html
    assert "no acepta esa especie" in html


def test_sin_postulantes_lo_dice(client, ficha):
    html = client.get(url(ficha)).content.decode()
    assert "No hay postulaciones de hogares habilitados" in html
    assert "Elegir este hogar" not in html


# Elegir


def test_al_elegir_vuelve_a_la_ficha_y_deja_el_resultado(client, ficha):
    elegido = crear_hogar("lucia")
    otro = crear_hogar("otro")
    p_elegida = postular(elegido, ficha)
    p_otro = postular(otro, ficha)

    respuesta = client.post(url(ficha), {"postulacion": p_elegida.pk})

    assert respuesta.status_code == 302
    assert respuesta.url == f"{reverse('fichas:detalle', args=[ficha.pk])}?elegido=1"
    p_elegida.refresh_from_db()
    p_otro.refresh_from_db()
    assert p_elegida.estado == Postulacion.Estado.ELEGIDA
    assert p_otro.estado == Postulacion.Estado.DESCARTADA
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.EN_ADOPCION
    assert Notificacion.objects.count() == 2


def test_si_el_hogar_ya_no_esta_habilitado_vuelve_a_la_lista_y_no_cambia_nada(client, ficha):
    suspendido = crear_hogar("suspendido")
    bueno = crear_hogar("bueno")
    p_suspendido = postular(suspendido, ficha)
    p_bueno = postular(bueno, ficha)
    suspender(suspendido)

    respuesta = client.post(url(ficha), {"postulacion": p_suspendido.pk})
    html = respuesta.content.decode()

    assert respuesta.status_code == 200
    assert "ya no está habilitado" in html
    assert "Bueno" in html
    p_suspendido.refresh_from_db()
    p_bueno.refresh_from_db()
    assert p_suspendido.estado == Postulacion.Estado.PENDIENTE
    assert p_bueno.estado == Postulacion.Estado.PENDIENTE
    assert Notificacion.objects.count() == 0


@pytest.mark.parametrize("valor", ["", "abc", "999999"])
def test_una_postulacion_que_no_existe_vuelve_con_el_error(client, ficha, valor):
    postular(crear_hogar("lucia"), ficha)

    respuesta = client.post(url(ficha), {"postulacion": valor})

    assert respuesta.status_code == 200
    assert "ya no está disponible" in respuesta.content.decode()


def test_una_postulacion_de_otra_ficha_no_se_puede_elegir(client, ficha):
    de_otra = postular(crear_hogar("lucia"), crear_ficha())

    respuesta = client.post(url(ficha), {"postulacion": de_otra.pk})

    assert "ya no está disponible" in respuesta.content.decode()
    de_otra.refresh_from_db()
    assert de_otra.estado == Postulacion.Estado.PENDIENTE


def test_con_un_hogar_ya_elegido_no_se_ofrece_elegir_otro(client, ficha):
    postular(crear_hogar("elegido"), ficha, estado=Postulacion.Estado.ELEGIDA)
    nueva = postular(crear_hogar("nueva"), ficha)

    html = client.get(url(ficha)).content.decode()
    assert "Ya hay un hogar elegido" in html
    assert "Elegir este hogar" not in html

    respuesta = client.post(url(ficha), {"postulacion": nueva.pk})
    assert "Ya hay un hogar elegido" in respuesta.content.decode()
    nueva.refresh_from_db()
    assert nueva.estado == Postulacion.Estado.PENDIENTE
