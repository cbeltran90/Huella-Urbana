import pytest
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


def test_contrasena_de_nueve_caracteres_se_rechaza():
    with pytest.raises(ValidationError) as error:
        validate_password("Zq7mWp3xK")
    codigos = [e.code for e in error.value.error_list]
    assert "password_too_short" in codigos


def test_contrasena_de_diez_caracteres_se_acepta():
    validate_password("Zq7mWp3xKd")
