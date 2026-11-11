import smtplib

import pytest
from django.conf import settings
from django.test import RequestFactory, override_settings

from apps.cuentas import servicios
from apps.cuentas.models import Usuario

pytestmark = pytest.mark.django_db


def test_el_correo_tiene_un_tiempo_de_espera():
    assert settings.EMAIL_TIMEOUT is not None
    assert settings.EMAIL_TIMEOUT > 0


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
    EMAIL_HOST="correo.invalido",
    EMAIL_TIMEOUT=3,
)
def test_el_envio_usa_el_tiempo_de_espera_y_un_timeout_no_rompe_el_pedido(monkeypatch):
    recibidos = {}

    def smtp_que_no_responde(*args, **kwargs):
        recibidos.update(kwargs)
        raise TimeoutError("timed out")

    monkeypatch.setattr(smtplib, "SMTP", smtp_que_no_responde)
    usuario = Usuario.objects.create_user("ana@example.com", "Ana", "clave-de-prueba-1")

    enviado = servicios.enviar_correo_confirmacion(usuario, RequestFactory().get("/"))

    assert enviado is False
    assert recibidos["timeout"] == 3
