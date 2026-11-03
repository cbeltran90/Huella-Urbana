from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.cuentas.models import EstadoCuenta, Sancion, Usuario

CLAVE = "clave-de-prueba-1"


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def crear(usuario, tipo, **campos):
    return Sancion.objects.create(
        usuario=usuario,
        email_hash=usuario.email_hash,
        tipo=tipo,
        motivo="Motivo de prueba",
        **campos,
    )


@pytest.mark.django_db
def test_una_temporal_con_fin_futuro_esta_vigente(ana):
    sancion = crear(ana, Sancion.Tipo.TEMPORAL, fin=timezone.now() + timedelta(days=7))
    assert list(Sancion.objects.vigentes()) == [sancion]


@pytest.mark.django_db
def test_una_permanente_esta_vigente(ana):
    sancion = crear(ana, Sancion.Tipo.PERMANENTE)
    assert list(Sancion.objects.vigentes()) == [sancion]


@pytest.mark.django_db
def test_una_temporal_vencida_no_esta_vigente(ana):
    crear(
        ana,
        Sancion.Tipo.TEMPORAL,
        inicio=timezone.now() - timedelta(days=8),
        fin=timezone.now() - timedelta(days=1),
    )
    assert not Sancion.objects.vigentes().exists()


@pytest.mark.django_db
def test_una_sancion_levantada_no_esta_vigente(ana):
    crear(ana, Sancion.Tipo.PERMANENTE, revocada_en=timezone.now())
    assert not Sancion.objects.vigentes().exists()


@pytest.mark.django_db
def test_una_sancion_que_todavia_no_empezo_no_esta_vigente(ana):
    crear(ana, Sancion.Tipo.PERMANENTE, inicio=timezone.now() + timedelta(days=1))
    assert not Sancion.objects.vigentes().exists()


@pytest.mark.django_db
def test_una_temporal_sin_fecha_de_fin_se_rechaza(ana):
    with pytest.raises(IntegrityError), transaction.atomic():
        crear(ana, Sancion.Tipo.TEMPORAL)


@pytest.mark.django_db
def test_una_permanente_con_fecha_de_fin_se_rechaza(ana):
    with pytest.raises(IntegrityError), transaction.atomic():
        crear(ana, Sancion.Tipo.PERMANENTE, fin=timezone.now() + timedelta(days=7))


@pytest.mark.django_db
def test_la_sancion_sobrevive_si_se_elimina_la_cuenta(ana):
    sancion = crear(ana, Sancion.Tipo.PERMANENTE)
    huella = ana.email_hash

    ana.delete()
    sancion.refresh_from_db()

    assert sancion.usuario is None
    assert sancion.email_hash == huella
