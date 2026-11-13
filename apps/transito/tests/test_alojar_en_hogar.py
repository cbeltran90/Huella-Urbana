from datetime import timedelta

import pytest
from django.utils import timezone

from apps.cuentas.models import EstadoCuenta, Sancion, Usuario
from apps.fichas.models import FichaAnimal
from apps.transito import ingreso
from apps.transito.models import Alojamiento, PerfilTransito
from apps.transito.servicios import cupo_libre

CLAVE = "clave-de-prueba-1"

pytestmark = pytest.mark.django_db


def crear_hogar(nombre, **perfil):
    usuario = Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    datos = {
        "especies_aceptadas": "perro",
        "tamano_maximo": "grande",
        "duracion_maxima_dias": 30,
        "cupo_declarado": 1,
        **perfil,
    }
    PerfilTransito.objects.create(usuario=usuario, **datos)
    return usuario


@pytest.fixture
def ficha():
    return FichaAnimal.objects.create(nombre="Firulais", especie="perro", tamano="mediano")


def test_crea_el_alojamiento_con_fecha_de_fin_y_sanidad(ficha):
    hogar = crear_hogar("hogar")

    alojamiento = ingreso.alojar_en_hogar(ficha, hogar, vacunado=True, castrado=True)

    hoy = timezone.localdate()
    assert alojamiento.ficha == ficha
    assert alojamiento.hogar.usuario == hogar
    assert alojamiento.fecha_ingreso == hoy
    assert alojamiento.fecha_fin_prevista == hoy + timedelta(days=30)
    assert alojamiento.vacunado_al_ingreso is True
    assert alojamiento.castrado_al_ingreso is True
    assert alojamiento.desparasitado_al_ingreso is False


def test_el_hogar_ocupa_una_plaza(ficha):
    hogar = crear_hogar("hogar")
    perfil = PerfilTransito.objects.get(usuario=hogar)

    ingreso.alojar_en_hogar(ficha, hogar)

    assert cupo_libre(perfil) == 0


def test_si_venia_de_otro_hogar_se_cierra_ese_alojamiento_por_relevo(ficha):
    anterior = crear_hogar("anterior")
    nuevo = crear_hogar("nuevo")
    primero = ingreso.alojar_en_hogar(ficha, anterior)

    ingreso.alojar_en_hogar(ficha, nuevo)

    primero.refresh_from_db()
    assert primero.fecha_fin_real == timezone.localdate()
    assert primero.motivo_fin == Alojamiento.MotivoFin.RELEVO
    assert cupo_libre(PerfilTransito.objects.get(usuario=anterior)) == 1


def test_un_hogar_sin_perfil_activo_no_puede_alojar(ficha):
    hogar = crear_hogar("hogar")
    PerfilTransito.objects.filter(usuario=hogar).update(activo=False)

    with pytest.raises(ingreso.IngresoNoPermitido):
        ingreso.alojar_en_hogar(ficha, hogar)

    assert not Alojamiento.objects.exists()


def test_un_hogar_suspendido_no_puede_alojar(ficha):
    hogar = crear_hogar("hogar")
    Sancion.objects.create(
        usuario=hogar,
        email_hash=hogar.email_hash,
        tipo=Sancion.Tipo.TEMPORAL,
        motivo="Motivo de prueba",
        fin=timezone.now() + timedelta(days=3),
    )

    with pytest.raises(ingreso.IngresoNoPermitido):
        ingreso.alojar_en_hogar(ficha, hogar)

    assert not Alojamiento.objects.exists()
