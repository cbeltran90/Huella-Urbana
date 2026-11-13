from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.fichas.models import FichaAnimal
from apps.publicaciones.models import Publicacion

pytestmark = pytest.mark.django_db


def cargar(**opciones):
    salida = StringIO()
    call_command("cargar_demo", stdout=salida, **opciones)
    return salida.getvalue()


def test_carga_los_recorridos_de_transito_adopcion_y_extravio():
    cargar()

    for nombre in ("Lola", "Toto", "Nube", "Rocco", "Mora", "Nina", "Pipo"):
        assert FichaAnimal.objects.filter(nombre=nombre).exists(), nombre
    assert Publicacion.objects.filter(ficha__nombre="Nina", tipo="extravio").count() == 1


def test_crea_las_cuentas_de_cada_recorrido():
    cargar()

    correos = set(get_user_model().objects.values_list("email", flat=True))
    assert {
        "moderador@demo.huella.test",
        "lucia@demo.huella.test",
        "camila@demo.huella.test",
    } <= correos


def test_se_puede_correr_dos_veces_sin_duplicar():
    cargar()
    fichas = FichaAnimal.objects.count()
    publicaciones = Publicacion.objects.count()

    cargar()

    assert FichaAnimal.objects.count() == fichas
    assert Publicacion.objects.count() == publicaciones


def test_la_contrasena_elegida_va_a_las_cuentas():
    cargar(password="otra-clave-2026")

    camila = get_user_model().objects.get(email="camila@demo.huella.test")
    assert camila.check_password("otra-clave-2026")
