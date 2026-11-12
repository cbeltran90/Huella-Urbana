from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import EstadoCuenta, Rol, Sancion, Usuario
from apps.fichas.models import FichaAnimal
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
    return Postulacion.objects.create(
        ficha=ficha,
        usuario=usuario,
        tipo=Postulacion.Tipo.TRANSITO,
        contacto=contacto,
        **campos,
    )


def detalle(client, ficha, consulta=""):
    return client.get(reverse("fichas:detalle", args=[ficha.pk]) + consulta).content.decode()


def enlace(ficha):
    return reverse("transito:elegir_hogar", args=[ficha.pk])


@pytest.fixture
def carla(client):
    usuario = crear_usuario("carla")
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


def test_el_cuidador_ve_cuantos_hay_y_el_enlace(client, carla):
    ficha = crear_ficha(cuidador=carla)
    postular(crear_hogar("uno"), ficha)

    html = detalle(client, ficha)
    assert enlace(ficha) in html
    assert "Hay 1 postulación de hogares" in html

    postular(crear_hogar("dos"), ficha)
    assert "Hay 2 postulaciones de hogares" in detalle(client, ficha)


def test_no_cuenta_a_los_hogares_no_habilitados(client, carla):
    ficha = crear_ficha(cuidador=carla)
    en_pausa = crear_hogar(
        "pausa", disponibilidad=False, pausa_hasta=timezone.localdate() + timedelta(days=10)
    )
    postular(en_pausa, ficha)

    assert enlace(ficha) not in detalle(client, ficha)


def test_sin_postulantes_no_hay_enlace(client, carla):
    ficha = crear_ficha(cuidador=carla)
    assert enlace(ficha) not in detalle(client, ficha)


def test_un_moderador_ve_el_enlace(client):
    ficha = crear_ficha(cuidador=crear_usuario("carla"))
    postular(crear_hogar("lucia"), ficha)
    client.force_login(crear_usuario("mora", rol=Rol.MODERADOR), backend=BACKEND_MODELO)

    assert enlace(ficha) in detalle(client, ficha)


def test_un_hogar_postulante_un_ajeno_y_un_visitante_no_ven_el_enlace(client):
    ficha = crear_ficha(cuidador=crear_usuario("carla"))
    hogar = crear_hogar("lucia")
    postular(hogar, ficha)

    assert enlace(ficha) not in detalle(client, ficha)  # visitante
    client.force_login(hogar, backend=BACKEND_MODELO)
    assert enlace(ficha) not in detalle(client, ficha)
    client.force_login(crear_usuario("ana"), backend=BACKEND_MODELO)
    assert enlace(ficha) not in detalle(client, ficha)


def test_con_otro_estado_no_hay_enlace(client, carla):
    ficha = crear_ficha(cuidador=carla, estado=FichaAnimal.Estado.EN_TRANSITO)
    postular(crear_hogar("lucia"), ficha)

    assert enlace(ficha) not in detalle(client, ficha)


def test_una_cuenta_suspendida_no_ve_el_enlace(client, carla):
    ficha = crear_ficha(cuidador=carla)
    postular(crear_hogar("lucia"), ficha)
    Sancion.objects.create(
        usuario=carla,
        email_hash=carla.email_hash,
        tipo=Sancion.Tipo.TEMPORAL,
        motivo="Motivo de prueba",
        fin=timezone.now() + timedelta(days=3),
    )

    assert enlace(ficha) not in detalle(client, ficha)


def test_con_un_hogar_elegido_se_ve_quien_es_con_su_contacto_y_no_el_enlace(client, carla):
    ficha = crear_ficha(cuidador=carla)
    postular(crear_hogar("lucia"), ficha, contacto="lucia@example.com", estado="elegida")
    postular(crear_hogar("otro"), ficha)

    html = detalle(client, ficha)

    assert "Hogar de tránsito elegido" in html
    assert "Lucia" in html
    assert "lucia@example.com" in html
    assert enlace(ficha) not in html


def test_el_cartel_de_elegido_solo_sale_si_de_verdad_hay_un_elegido(client, carla):
    ficha = crear_ficha(cuidador=carla)
    assert "Elegiste al hogar de tránsito" not in detalle(client, ficha, "?elegido=1")

    postular(crear_hogar("lucia"), ficha, estado="elegida")
    assert "Elegiste al hogar de tránsito" in detalle(client, ficha, "?elegido=1")
    assert "Elegiste al hogar de tránsito" not in detalle(client, ficha)
