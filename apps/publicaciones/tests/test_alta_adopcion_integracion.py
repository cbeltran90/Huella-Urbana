"""El alta directa en adopción con las piezas reales de A y C (sin simular nada)."""

import pytest

from apps.cuentas.models import EstadoCuenta
from apps.notificaciones.models import Notificacion
from apps.publicaciones import servicios
from apps.transito.models import PerfilTransito

from .conftest import crear_imagen

pytestmark = pytest.mark.django_db

ANIMAL = {"especie": "perro", "tamano": "mediano", "nombre": "Firulais", "color": "negro"}


def _hogar(django_user_model, correo, **perfil):
    usuario = django_user_model.objects.create_user(
        correo, "Hogar", "clave-de-prueba-1", estado_cuenta=EstadoCuenta.ACTIVA
    )
    datos = {
        "especies_aceptadas": "perro,gato",
        "tamano_maximo": "grande",
        "duracion_maxima_dias": 30,
        "cupo_declarado": 2,
        **perfil,
    }
    PerfilTransito.objects.create(usuario=usuario, **datos)
    return usuario


def test_un_hogar_compatible_recibe_su_aviso(ana, django_user_model, con_domicilio):
    hogar = _hogar(django_user_model, "hogar@ejemplo.com")

    publicacion = servicios.alta_en_adopcion(ana, animal=ANIMAL, archivos=[crear_imagen()])

    aviso = Notificacion.objects.get(usuario=hogar)
    assert aviso.tipo == "coincidencia_transito"
    assert aviso.ficha == publicacion.ficha
    assert aviso.publicacion == publicacion


def test_un_hogar_que_no_acepta_la_especie_no_recibe_aviso(ana, django_user_model, con_domicilio):
    _hogar(django_user_model, "hogar@ejemplo.com", especies_aceptadas="gato")

    servicios.alta_en_adopcion(ana, animal=ANIMAL, archivos=[crear_imagen()])

    assert not Notificacion.objects.exists()


def test_quien_da_el_animal_en_adopcion_no_se_avisa_a_si_mismo(ana, con_domicilio):
    PerfilTransito.objects.create(
        usuario=ana,
        especies_aceptadas="perro,gato",
        tamano_maximo="grande",
        duracion_maxima_dias=30,
        cupo_declarado=2,
    )

    servicios.alta_en_adopcion(ana, animal=ANIMAL, archivos=[crear_imagen()])

    assert not Notificacion.objects.filter(usuario=ana).exists()
