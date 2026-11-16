"""Configuración común a todos los tests."""

import pytest


@pytest.fixture(autouse=True)
def _contrasenas_rapidas(settings):
    # El algoritmo de producción (PBKDF2) es lento a propósito; en los tests no hace falta.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
