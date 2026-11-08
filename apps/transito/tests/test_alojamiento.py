from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone
from model_bakery import baker

from apps.cuentas.eliminacion import impedimentos_para_eliminar
from apps.cuentas.models import EstadoCuenta, Usuario
from apps.fichas.models import FichaAnimal
from apps.transito import servicios
from apps.transito.models import Alojamiento, PerfilTransito

CLAVE = "clave-de-prueba-1"

pytestmark = pytest.mark.django_db


def crear_hogar(nombre, cupo=2):
    usuario = Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    PerfilTransito.objects.create(
        usuario=usuario,
        especies_aceptadas="perro",
        tamano_maximo="mediano",
        duracion_maxima_dias=30,
        cupo_declarado=cupo,
    )
    return usuario


def alojar(usuario, ficha=None, **campos):
    hoy = timezone.localdate()
    return Alojamiento.objects.create(
        ficha=ficha or baker.make(FichaAnimal, especie="perro"),
        hogar=usuario.perfil_transito,
        fecha_fin_prevista=hoy + timedelta(days=30),
        **campos,
    )


def test_cuenta_solo_los_alojamientos_abiertos_del_hogar():
    ana, beto = crear_hogar("ana"), crear_hogar("beto")
    alojar(ana)
    alojar(ana, fecha_fin_real=timezone.localdate())
    alojar(beto)

    assert servicios.animales_alojados(ana) == 1


def test_el_cupo_libre_descuenta_los_alojados_reales():
    ana = crear_hogar("ana", cupo=3)
    alojar(ana)

    assert servicios.cupo_libre(ana.perfil_transito) == 2


def test_con_un_animal_alojado_no_se_puede_desactivar_el_perfil():
    ana = crear_hogar("ana")
    alojar(ana)

    with pytest.raises(servicios.DesactivacionNoPermitida):
        servicios.desactivar_perfil_transito(ana)


def test_con_un_animal_alojado_no_se_puede_eliminar_la_cuenta():
    ana = crear_hogar("ana")
    alojar(ana)

    codigos = [impedimento.codigo for impedimento in impedimentos_para_eliminar(ana)]
    assert "fichas_en_circuito" in codigos


def test_un_animal_no_puede_tener_dos_alojamientos_abiertos():
    ana, beto = crear_hogar("ana"), crear_hogar("beto")
    ficha = baker.make(FichaAnimal, especie="perro")
    alojar(ana, ficha)

    with pytest.raises(IntegrityError), transaction.atomic():
        alojar(beto, ficha)


def test_un_animal_puede_volver_a_alojarse_despues_de_cerrar_el_anterior():
    ana, beto = crear_hogar("ana"), crear_hogar("beto")
    ficha = baker.make(FichaAnimal, especie="perro")
    alojar(ana, ficha, fecha_fin_real=timezone.localdate())

    alojar(beto, ficha)

    assert ficha.alojamientos.count() == 2


def test_no_se_puede_borrar_una_ficha_con_alojamientos():
    ana = crear_hogar("ana")
    alojamiento = alojar(ana)

    with pytest.raises(ProtectedError):
        alojamiento.ficha.delete()
