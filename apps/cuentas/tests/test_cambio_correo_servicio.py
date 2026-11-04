import re

import pytest
from django.core.cache import caches
from django.test import RequestFactory

from apps.cuentas import servicios
from apps.cuentas.models import EstadoCuenta, Rol, Sancion, Usuario, hash_email
from apps.cuentas.servicios import CambioCorreoInvalido

CLAVE = "clave-de-prueba-1"
NUEVO = "nuevo@example.com"


@pytest.fixture(autouse=True)
def sin_esperas():
    caches["reenvios"].clear()
    yield
    caches["reenvios"].clear()


@pytest.fixture
def ana(db):
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


@pytest.fixture
def moderadora(db):
    return Usuario.objects.create_user(
        "mod@example.com", "Mod", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, rol=Rol.MODERADOR
    )


def pedir(usuario, correo=NUEVO):
    return servicios.solicitar_cambio_correo(usuario, correo, RequestFactory().get("/"))


def token_del_correo(mailoutbox):
    return re.search(r"/cuentas/correo/confirmar/([^/\s]+)/", mailoutbox[-1].body).group(1)


@pytest.mark.django_db
def test_se_envia_el_enlace_al_correo_nuevo_y_el_actual_no_cambia(ana, mailoutbox):
    assert pedir(ana) is True

    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == [NUEVO]
    assert "/cuentas/correo/confirmar/" in mailoutbox[0].body
    ana.refresh_from_db()
    assert ana.email == "ana@example.com"


@pytest.mark.django_db
def test_el_correo_nuevo_se_normaliza(ana, mailoutbox):
    pedir(ana, "  NUEVO@Example.com ")
    assert mailoutbox[0].to == [NUEVO]


@pytest.mark.django_db
def test_el_enlace_del_correo_aplica_el_cambio(ana, mailoutbox):
    pedir(ana)

    servicios.confirmar_cambio_correo(token_del_correo(mailoutbox))

    ana.refresh_from_db()
    assert ana.email == NUEVO
    assert ana.email_hash == hash_email(NUEVO)
    assert Usuario.objects.get(email=NUEVO) == ana


@pytest.mark.django_db
def test_el_enlace_sirve_una_sola_vez(ana, mailoutbox):
    pedir(ana)
    token = token_del_correo(mailoutbox)
    servicios.confirmar_cambio_correo(token)

    with pytest.raises(CambioCorreoInvalido) as error:
        servicios.confirmar_cambio_correo(token)

    assert str(error.value) == servicios.MENSAJE_ENLACE_CORREO_INVALIDO


@pytest.mark.django_db
def test_aplicar_un_enlace_invalida_los_otros_pendientes(ana):
    primero = servicios.crear_token_cambio_correo(ana, "uno@example.com")
    segundo = servicios.crear_token_cambio_correo(ana, "dos@example.com")
    servicios.confirmar_cambio_correo(primero)

    with pytest.raises(CambioCorreoInvalido):
        servicios.confirmar_cambio_correo(segundo)

    ana.refresh_from_db()
    assert ana.email == "uno@example.com"


@pytest.mark.django_db
def test_un_enlace_vencido_no_aplica_el_cambio(ana, mailoutbox, monkeypatch):
    pedir(ana)
    monkeypatch.setattr(servicios, "DIAS_VIGENCIA_CAMBIO_CORREO", -1)

    with pytest.raises(CambioCorreoInvalido):
        servicios.confirmar_cambio_correo(token_del_correo(mailoutbox))

    ana.refresh_from_db()
    assert ana.email == "ana@example.com"


@pytest.mark.django_db
def test_un_enlace_alterado_no_sirve(ana, mailoutbox):
    pedir(ana)
    token = token_del_correo(mailoutbox)

    with pytest.raises(CambioCorreoInvalido):
        servicios.confirmar_cambio_correo(token[:-2] + "xx")

    ana.refresh_from_db()
    assert ana.email == "ana@example.com"


@pytest.mark.django_db
def test_el_mismo_correo_de_la_cuenta_se_rechaza(ana, mailoutbox):
    with pytest.raises(CambioCorreoInvalido) as error:
        pedir(ana, "ANA@example.com")
    assert str(error.value) == servicios.MENSAJE_CORREO_IGUAL
    assert mailoutbox == []


@pytest.mark.django_db
def test_un_correo_de_otra_cuenta_se_rechaza(ana, mailoutbox):
    Usuario.objects.create_user(
        "beto@example.com", "Beto", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    with pytest.raises(CambioCorreoInvalido) as error:
        pedir(ana, "BETO@example.com")
    assert str(error.value) == servicios.MENSAJE_CORREO_USADO
    assert mailoutbox == []


@pytest.mark.django_db
def test_un_correo_con_suspension_permanente_se_rechaza(ana, moderadora, mailoutbox):
    otro = Usuario.objects.create_user(
        "perm@example.com", "Perm", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    servicios.sancionar(otro, Sancion.Tipo.PERMANENTE, "Motivo", moderadora)
    otro.delete()  # la sanción queda con el hash del correo

    with pytest.raises(CambioCorreoInvalido) as error:
        pedir(ana, "perm@example.com")

    assert str(error.value) == servicios.MENSAJE_CORREO_SUSPENDIDO
    assert mailoutbox == []


@pytest.mark.django_db
def test_no_se_puede_pedir_otro_enlace_enseguida(ana, mailoutbox):
    pedir(ana)

    with pytest.raises(CambioCorreoInvalido) as error:
        pedir(ana, "otro@example.com")

    assert str(error.value) == servicios.MENSAJE_CAMBIO_RECIENTE
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_un_correo_rechazado_no_gasta_la_espera(ana, mailoutbox):
    with pytest.raises(CambioCorreoInvalido):
        pedir(ana, "ana@example.com")
    assert pedir(ana) is True


@pytest.mark.django_db
def test_si_falla_el_envio_se_puede_reintentar_sin_esperar(ana, mailoutbox, monkeypatch):
    def falla(*args, **kwargs):
        raise OSError("sin conexión")

    monkeypatch.setattr(servicios, "send_mail", falla)
    assert pedir(ana) is False

    monkeypatch.undo()
    assert pedir(ana) is True
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_si_otra_persona_toma_el_correo_antes_de_abrir_el_enlace_se_rechaza(ana, mailoutbox):
    pedir(ana)
    Usuario.objects.create_user(NUEVO, "Beto", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA)

    with pytest.raises(CambioCorreoInvalido) as error:
        servicios.confirmar_cambio_correo(token_del_correo(mailoutbox))

    assert str(error.value) == servicios.MENSAJE_CORREO_USADO
    ana.refresh_from_db()
    assert ana.email == "ana@example.com"


@pytest.mark.django_db
def test_una_cuenta_sancionada_despues_de_pedirlo_no_cambia_el_correo(ana, moderadora, mailoutbox):
    pedir(ana)
    servicios.sancionar(ana, Sancion.Tipo.TEMPORAL, "Motivo", moderadora)

    with pytest.raises(CambioCorreoInvalido) as error:
        servicios.confirmar_cambio_correo(token_del_correo(mailoutbox))

    assert str(error.value) == servicios.MENSAJE_CUENTA_SIN_CAMBIO_DE_CORREO
    ana.refresh_from_db()
    assert ana.email == "ana@example.com"
