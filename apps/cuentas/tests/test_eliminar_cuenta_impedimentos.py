from datetime import timedelta

import pytest
from django.utils import timezone

from apps.cuentas import eliminacion
from apps.cuentas.models import EstadoCuenta, Sancion, Usuario
from apps.fichas.models import FichaAnimal
from apps.transito import servicios as servicios_transito

CLAVE = "clave-de-prueba-1"
Estado = FichaAnimal.Estado

pytestmark = pytest.mark.django_db


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


@pytest.fixture
def otra():
    return Usuario.objects.create_user(
        "otra@example.com", "Otra", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def ficha(estado, **campos):
    return FichaAnimal.objects.create(especie="perro", estado=estado, **campos)


def sancionar(usuario, tipo, **campos):
    return Sancion.objects.create(
        usuario=usuario,
        email_hash=usuario.email_hash,
        tipo=tipo,
        motivo="Motivo de prueba",
        **campos,
    )


def codigos(usuario):
    return [impedimento.codigo for impedimento in eliminacion.impedimentos_para_eliminar(usuario)]


def test_una_cuenta_sin_nada_pendiente_se_puede_eliminar(ana):
    assert eliminacion.impedimentos_para_eliminar(ana) == []


def test_una_suspension_temporal_vigente_lo_impide_y_muestra_la_fecha_de_fin(ana):
    fin = timezone.now() + timedelta(days=7)
    sancionar(ana, Sancion.Tipo.TEMPORAL, fin=fin)

    (impedimento,) = eliminacion.impedimentos_para_eliminar(ana)

    assert impedimento.codigo == "suspension_temporal"
    assert impedimento.fin == fin
    assert timezone.localtime(fin).strftime("%d/%m/%Y %H:%M") in impedimento.mensaje


def test_una_suspension_temporal_vencida_no_lo_impide(ana):
    sancionar(
        ana,
        Sancion.Tipo.TEMPORAL,
        inicio=timezone.now() - timedelta(days=8),
        fin=timezone.now() - timedelta(days=1),
    )
    assert codigos(ana) == []


def test_una_suspension_permanente_no_lo_impide(ana):
    sancionar(ana, Sancion.Tipo.PERMANENTE)
    assert codigos(ana) == []


@pytest.mark.parametrize(
    ("estado", "campo"),
    [
        (Estado.EN_ADOPCION, "responsable"),
        (Estado.EN_ADOPCION, "cuidador"),
        (Estado.EN_TRANSITO, "responsable"),
        (Estado.EN_TRANSITO, "cuidador"),
        (Estado.SIN_RESPONSABLE, "cuidador"),
    ],
)
def test_una_ficha_en_el_circuito_lo_impide_y_se_lista(ana, estado, campo):
    en_circuito = ficha(estado, **{campo: ana})

    (impedimento,) = eliminacion.impedimentos_para_eliminar(ana)

    assert impedimento.codigo == "fichas_en_circuito"
    assert impedimento.fichas == (en_circuito,)


@pytest.mark.parametrize(
    ("estado", "campo"),
    [
        (Estado.REGISTRADO, "responsable"),
        (Estado.REGISTRADO, "cuidador"),
        (Estado.SIN_RESPONSABLE, "responsable"),
    ],
)
def test_las_fichas_fuera_del_circuito_no_lo_impiden(ana, estado, campo):
    ficha(estado, **{campo: ana})
    assert codigos(ana) == []


def test_las_fichas_de_otra_persona_no_cuentan(ana, otra):
    ficha(Estado.EN_ADOPCION, responsable=otra, cuidador=otra)
    assert codigos(ana) == []


def test_se_listan_todas_las_fichas_que_hay_que_resolver(ana):
    primera = ficha(Estado.EN_ADOPCION, responsable=ana)
    segunda = ficha(Estado.SIN_RESPONSABLE, cuidador=ana)

    (impedimento,) = eliminacion.impedimentos_para_eliminar(ana)

    assert impedimento.fichas == (primera, segunda)


def test_un_hogar_con_animales_alojados_no_puede_eliminar_la_cuenta(ana, monkeypatch):
    monkeypatch.setattr(servicios_transito, "animales_alojados", lambda usuario: 1)

    (impedimento,) = eliminacion.impedimentos_para_eliminar(ana)

    assert impedimento.codigo == "fichas_en_circuito"
    assert impedimento.fichas == ()


def test_una_eleccion_pendiente_lo_impide(ana, monkeypatch):
    monkeypatch.setattr(servicios_transito, "tiene_eleccion_pendiente", lambda usuario: True)

    (impedimento,) = eliminacion.impedimentos_para_eliminar(ana)

    assert impedimento.codigo == "eleccion_pendiente"
    assert impedimento.mensaje == eliminacion.MENSAJE_ELECCION_PENDIENTE


def test_hoy_no_hay_eleccion_pendiente_porque_no_existen_las_postulaciones(ana):
    assert servicios_transito.tiene_eleccion_pendiente(ana) is False


def test_se_informan_todos_los_impedimentos_a_la_vez(ana, monkeypatch):
    sancionar(ana, Sancion.Tipo.TEMPORAL, fin=timezone.now() + timedelta(days=3))
    ficha(Estado.EN_TRANSITO, cuidador=ana)
    monkeypatch.setattr(servicios_transito, "tiene_eleccion_pendiente", lambda usuario: True)

    assert codigos(ana) == ["suspension_temporal", "fichas_en_circuito", "eleccion_pendiente"]
