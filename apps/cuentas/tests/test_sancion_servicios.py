from datetime import timedelta

import pytest
from constance.test import override_config
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from apps.cuentas import servicios
from apps.cuentas.models import EstadoCuenta, Rol, Sancion, Usuario

CLAVE = "clave-de-prueba-1"
TEMPORAL = Sancion.Tipo.TEMPORAL
PERMANENTE = Sancion.Tipo.PERMANENTE


def _usuario(email, nombre, **campos):
    return Usuario.objects.create_user(
        email, nombre, CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, **campos
    )


@pytest.fixture
def ana():
    return _usuario("ana@example.com", "Ana")


@pytest.fixture
def beto():
    return _usuario("beto@example.com", "Beto")


@pytest.fixture
def moderadora():
    return _usuario("mod@example.com", "Moderadora", rol=Rol.MODERADOR)


@pytest.fixture
def administrador():
    return _usuario("admin@example.com", "Admin", rol=Rol.ADMINISTRADOR)


def _crear(usuario, tipo, **campos):
    return Sancion.objects.create(
        usuario=usuario,
        email_hash=usuario.email_hash,
        tipo=tipo,
        motivo="Motivo de prueba",
        **campos,
    )


def _en_siete_dias():
    return timezone.now() + timedelta(days=7)


# --- qué sanción corresponde ---


@pytest.mark.django_db
def test_la_primera_vez_corresponde_la_temporal(ana):
    assert servicios.tipo_sugerido(ana) == TEMPORAL


@pytest.mark.django_db
def test_la_segunda_vez_corresponde_la_permanente(ana):
    _crear(
        ana,
        TEMPORAL,
        inicio=timezone.now() - timedelta(days=30),
        fin=timezone.now() - timedelta(days=23),
    )
    assert servicios.tipo_sugerido(ana) == PERMANENTE


@pytest.mark.django_db
def test_una_sancion_levantada_no_cuenta_como_antecedente(ana):
    _crear(ana, TEMPORAL, fin=_en_siete_dias(), revocada_en=timezone.now())
    assert servicios.tipo_sugerido(ana) == TEMPORAL


# --- aplicar ---


@pytest.mark.django_db
def test_la_temporal_dura_los_dias_configurados(ana, moderadora):
    sancion = servicios.sancionar(ana, TEMPORAL, "Publicó contenido ofensivo", moderadora)

    esperado = timezone.now() + timedelta(days=7)
    assert abs(sancion.fin - esperado) < timedelta(minutes=1)
    assert sancion.usuario == ana
    assert sancion.aplicada_por == moderadora
    assert sancion.email_hash == ana.email_hash
    assert servicios.sancion_vigente(ana) == sancion


@pytest.mark.django_db
@override_config(DIAS_PRIMERA_SUSPENSION=3)
def test_la_duracion_sale_del_parametro(ana, moderadora):
    sancion = servicios.sancionar(ana, TEMPORAL, "Motivo", moderadora)
    esperado = timezone.now() + timedelta(days=3)
    assert abs(sancion.fin - esperado) < timedelta(minutes=1)


@pytest.mark.django_db
def test_la_permanente_no_vence(ana, moderadora):
    sancion = servicios.sancionar(ana, PERMANENTE, "Falta grave", moderadora)
    assert sancion.fin is None
    assert servicios.esta_suspendido(ana)


@pytest.mark.django_db
def test_un_administrador_tambien_puede_sancionar(ana, administrador):
    sancion = servicios.sancionar(ana, TEMPORAL, "Motivo", administrador)
    assert sancion.aplicada_por == administrador


@pytest.mark.django_db
def test_un_usuario_registrado_no_puede_sancionar(ana, beto):
    with pytest.raises(servicios.SancionNoPermitida):
        servicios.sancionar(ana, TEMPORAL, "Motivo", beto)
    assert not Sancion.objects.exists()


@pytest.mark.django_db
def test_nadie_puede_sancionarse_a_si_mismo(moderadora):
    with pytest.raises(servicios.SancionNoPermitida):
        servicios.sancionar(moderadora, TEMPORAL, "Motivo", moderadora)


@pytest.mark.django_db
def test_el_motivo_es_obligatorio(ana, moderadora):
    with pytest.raises(servicios.SancionNoPermitida):
        servicios.sancionar(ana, TEMPORAL, "   ", moderadora)
    assert not Sancion.objects.exists()


@pytest.mark.django_db
def test_no_se_puede_sancionar_dos_veces_a_la_vez(ana, moderadora):
    servicios.sancionar(ana, TEMPORAL, "Motivo", moderadora)
    with pytest.raises(servicios.SancionNoPermitida):
        servicios.sancionar(ana, PERMANENTE, "Otro motivo", moderadora)
    assert Sancion.objects.count() == 1


# --- levantar ---


@pytest.mark.django_db
def test_levantar_deja_a_la_cuenta_sin_sancion(ana, moderadora):
    sancion = servicios.sancionar(ana, PERMANENTE, "Motivo", moderadora)

    servicios.levantar_sancion(sancion, moderadora)

    sancion.refresh_from_db()
    assert sancion.revocada_por == moderadora
    assert sancion.revocada_en is not None
    assert servicios.sancion_vigente(ana) is None


@pytest.mark.django_db
def test_un_usuario_registrado_no_puede_levantar(ana, beto, moderadora):
    sancion = servicios.sancionar(ana, PERMANENTE, "Motivo", moderadora)
    with pytest.raises(servicios.SancionNoPermitida):
        servicios.levantar_sancion(sancion, beto)
    assert servicios.esta_suspendido(ana)


@pytest.mark.django_db
def test_no_se_puede_levantar_dos_veces(ana, moderadora):
    sancion = servicios.sancionar(ana, PERMANENTE, "Motivo", moderadora)
    servicios.levantar_sancion(sancion, moderadora)
    with pytest.raises(servicios.SancionNoPermitida):
        servicios.levantar_sancion(sancion, moderadora)


# --- consultar ---


@pytest.mark.django_db
def test_un_visitante_no_tiene_sancion():
    assert servicios.sancion_vigente(AnonymousUser()) is None


@pytest.mark.django_db
def test_si_hay_dos_vigentes_se_informa_la_permanente(ana):
    _crear(ana, TEMPORAL, fin=_en_siete_dias())
    permanente = _crear(ana, PERMANENTE)
    assert servicios.sancion_vigente(ana) == permanente


@pytest.mark.django_db
def test_correo_con_suspension_permanente_no_distingue_mayusculas(ana):
    _crear(ana, PERMANENTE)
    assert servicios.correo_con_suspension_permanente("  ANA@Example.com ")


@pytest.mark.django_db
def test_la_suspension_permanente_sigue_valiendo_si_se_elimina_la_cuenta(ana):
    _crear(ana, PERMANENTE)
    ana.delete()
    assert servicios.correo_con_suspension_permanente("ana@example.com")


@pytest.mark.django_db
def test_la_temporal_no_impide_registrarse(ana):
    _crear(ana, TEMPORAL, fin=_en_siete_dias())
    assert not servicios.correo_con_suspension_permanente("ana@example.com")


@pytest.mark.django_db
def test_una_permanente_levantada_no_impide_registrarse(ana):
    _crear(ana, PERMANENTE, revocada_en=timezone.now())
    assert not servicios.correo_con_suspension_permanente("ana@example.com")


# --- un moderador no toca a un administrador ---


@pytest.fixture
def otro_administrador():
    return _usuario("admin2@example.com", "Admin dos", rol=Rol.ADMINISTRADOR)


@pytest.mark.django_db
def test_un_moderador_no_puede_sancionar_a_un_administrador(administrador, moderadora):
    with pytest.raises(servicios.SancionNoPermitida):
        servicios.sancionar(administrador, TEMPORAL, "Motivo", moderadora)
    assert not Sancion.objects.exists()


@pytest.mark.django_db
def test_un_administrador_puede_sancionar_a_otro_administrador(administrador, otro_administrador):
    sancion = servicios.sancionar(otro_administrador, TEMPORAL, "Motivo", administrador)
    assert servicios.sancion_vigente(otro_administrador) == sancion


@pytest.mark.django_db
def test_un_moderador_no_puede_levantar_la_sancion_de_un_administrador(
    administrador, otro_administrador, moderadora
):
    sancion = servicios.sancionar(otro_administrador, TEMPORAL, "Motivo", administrador)
    with pytest.raises(servicios.SancionNoPermitida):
        servicios.levantar_sancion(sancion, moderadora)
    assert servicios.esta_suspendido(otro_administrador)
