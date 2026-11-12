from io import StringIO

import pytest
from django.core.management import call_command

from apps.adopcion import eleccion
from apps.fichas.models import FichaAnimal
from apps.transito import eleccion as eleccion_transito
from apps.transito.models import Postulacion

Estado = FichaAnimal.Estado

pytestmark = pytest.mark.django_db


def cargar():
    call_command("cargar_demo_adopcion", stdout=StringIO())


def ficha(nombre):
    return FichaAnimal.objects.get(nombre=nombre)


def pendientes(mascota, tipo):
    return mascota.postulaciones.filter(tipo=tipo, estado=Postulacion.Estado.PENDIENTE).count()


def test_cada_mascota_queda_en_su_paso_del_recorrido():
    cargar()

    assert ficha("Lola").estado == Estado.SIN_RESPONSABLE
    assert ficha("Toto").estado == Estado.EN_ADOPCION
    assert pendientes(ficha("Toto"), Postulacion.Tipo.TRANSITO) == 2
    assert eleccion_transito.hay_hogar_elegido(ficha("Nube"))
    assert ficha("Rocco").estado == Estado.EN_TRANSITO
    assert pendientes(ficha("Rocco"), Postulacion.Tipo.ADOPCION) == 2
    assert eleccion.elegida_de(ficha("Mora")).usuario.email == "ana@demo.huella.test"


def test_se_puede_correr_dos_veces_sin_duplicar():
    cargar()
    cargar()

    for nombre in ("Lola", "Toto", "Nube", "Rocco", "Mora"):
        assert FichaAnimal.objects.filter(nombre=nombre).count() == 1
