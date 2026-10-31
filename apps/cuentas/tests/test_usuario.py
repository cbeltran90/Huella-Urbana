import pytest


@pytest.mark.django_db
def test_crear_usuario(django_user_model):
    usuario = django_user_model.objects.create_user(
        email="ana@ejemplo.com", nombre_usuario="ana", password="clave-de-prueba"
    )
    assert usuario.check_password("clave-de-prueba")
    assert usuario.is_active is False  # Por defecto nace pendiente
    assert usuario.estado_cuenta == "pendiente"
    assert usuario.email == "ana@ejemplo.com"
    assert usuario.email_hash is not None
    assert not usuario.is_staff
