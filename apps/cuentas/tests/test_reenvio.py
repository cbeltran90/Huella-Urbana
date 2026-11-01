import re
from urllib.parse import urlparse

import pytest
from django.core.cache import caches
from django.urls import reverse

from apps.cuentas import servicios
from apps.cuentas.models import EstadoCuenta, Usuario

CLAVE = "clave-de-prueba-1"


@pytest.fixture(autouse=True)
def caché_limpia():
    caches["reenvios"].clear()


def pedir(client, email="ana@example.com"):
    return client.post(reverse("cuentas:reenviar"), {"email": email})


@pytest.mark.django_db
def test_una_cuenta_pendiente_recibe_un_enlace_nuevo(client, mailoutbox):
    Usuario.objects.create_user("ana@example.com", "Ana", CLAVE)
    respuesta = pedir(client)
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("cuentas:reenvio_listo")
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["ana@example.com"]


@pytest.mark.django_db
def test_el_enlace_reenviado_activa_la_cuenta(client, mailoutbox):
    Usuario.objects.create_user("ana@example.com", "Ana", CLAVE)
    pedir(client)
    ruta = urlparse(re.search(r"http://testserver\S+", mailoutbox[0].body).group(0)).path
    assert client.get(ruta).status_code == 200
    assert Usuario.objects.get(email="ana@example.com").estado_cuenta == EstadoCuenta.ACTIVA


@pytest.mark.django_db
def test_el_correo_se_busca_sin_importar_mayusculas(client, mailoutbox):
    Usuario.objects.create_user("ana@example.com", "Ana", CLAVE)
    pedir(client, " ANA@Example.com ")
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_un_correo_desconocido_recibe_la_misma_respuesta_y_nada_se_envia(client, mailoutbox):
    respuesta = pedir(client, "nadie@example.com")
    assert respuesta.status_code == 302
    assert respuesta.url == reverse("cuentas:reenvio_listo")
    assert mailoutbox == []


@pytest.mark.django_db
@pytest.mark.parametrize("estado", [EstadoCuenta.ACTIVA, EstadoCuenta.ELIMINADA])
def test_solo_las_cuentas_pendientes_reciben_el_enlace(client, mailoutbox, estado):
    Usuario.objects.create_user("ana@example.com", "Ana", CLAVE, estado_cuenta=estado)
    respuesta = pedir(client)
    assert respuesta.url == reverse("cuentas:reenvio_listo")
    assert mailoutbox == []


@pytest.mark.django_db
def test_dos_pedidos_seguidos_envian_un_solo_correo(client, mailoutbox):
    Usuario.objects.create_user("ana@example.com", "Ana", CLAVE)
    pedir(client)
    pedir(client)
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_si_falla_el_envio_la_respuesta_sigue_igual(client, monkeypatch):
    Usuario.objects.create_user("ana@example.com", "Ana", CLAVE)

    def falla(*args, **kwargs):
        raise OSError

    monkeypatch.setattr(servicios, "send_mail", falla)
    assert pedir(client).url == reverse("cuentas:reenvio_listo")


@pytest.mark.django_db
def test_un_correo_mal_escrito_muestra_el_error(client, mailoutbox):
    respuesta = pedir(client, "no-es-un-correo")
    assert respuesta.status_code == 200
    assert mailoutbox == []


@pytest.mark.django_db
def test_las_pantallas_de_espera_y_de_enlace_vencido_ofrecen_reenviar(client):
    destino = reverse("cuentas:reenviar")
    assert destino in client.get(reverse("cuentas:registro_listo")).content.decode()
    fallida = client.get("/cuentas/confirmar/token-falso/")
    assert destino in fallida.content.decode()
