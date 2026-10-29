import pytest


@pytest.mark.django_db
def test_crear_usuario(django_user_model):
    usuario = django_user_model.objects.create_user("ana", password="clave-de-prueba")
    assert usuario.check_password("clave-de-prueba")
    assert usuario.is_active
    assert not usuario.is_staff
