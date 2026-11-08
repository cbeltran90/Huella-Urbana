import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.cuentas.models import Rol
from apps.cuentas.servicios import esta_suspendido
from apps.fichas.models import FichaAnimal
from apps.transito import servicios
from apps.transito.models import PerfilTransito

pytestmark = pytest.mark.django_db


def _usuario(nombre):
    return get_user_model().objects.get(email=f"{nombre}@demo.huella.test")


def _perfil(nombre):
    return PerfilTransito.objects.get(usuario=_usuario(nombre))


def test_deja_cinco_hogares_un_moderador_y_a_bruno():
    call_command("cargar_demo_transito")

    assert PerfilTransito.objects.filter(activo=True).count() == 5
    assert _usuario("moderador").rol == Rol.MODERADOR
    bruno = FichaAnimal.objects.get(nombre="Bruno")
    assert (bruno.especie, bruno.tamano, bruno.requiere_medicacion) == ("perro", "grande", True)


def test_cada_hogar_queda_en_la_situacion_prevista():
    call_command("cargar_demo_transito")

    assert servicios.hogar_habilitado(_perfil("lucia"))
    assert servicios.hogar_habilitado(_perfil("martin"))
    assert servicios.hogar_habilitado(_perfil("romina"))
    assert not servicios.hogar_habilitado(_perfil("tomas"))  # en pausa
    assert not servicios.hogar_habilitado(_perfil("valeria"))  # suspendida
    assert esta_suspendido(_usuario("valeria"))


def test_solo_lucia_es_compatible_con_bruno():
    call_command("cargar_demo_transito")
    bruno = FichaAnimal.objects.get(nombre="Bruno")

    compatibles = servicios.hogares_compatibles(bruno)

    assert [perfil.usuario.email for perfil in compatibles] == ["lucia@demo.huella.test"]


def test_los_hogares_no_compatibles_muestran_por_que():
    call_command("cargar_demo_transito")
    bruno = FichaAnimal.objects.get(nombre="Bruno")

    assert len(servicios.incompatibilidades(_perfil("martin"), bruno)) == 3
    assert len(servicios.incompatibilidades(_perfil("romina"), bruno)) == 1
    assert servicios.incompatibilidades(_perfil("lucia"), bruno) == []


def test_se_puede_correr_dos_veces_sin_duplicar():
    call_command("cargar_demo_transito")
    call_command("cargar_demo_transito")

    assert PerfilTransito.objects.count() == 5
    assert get_user_model().objects.count() == 6
    assert FichaAnimal.objects.filter(nombre="Bruno").count() == 1


def test_la_contrasena_se_puede_elegir():
    call_command("cargar_demo_transito", password="otra-clave-1")

    assert _usuario("lucia").check_password("otra-clave-1")


def test_muestra_el_resumen(capsys):
    call_command("cargar_demo_transito")

    salida = capsys.readouterr().out
    assert "lucia@demo.huella.test: se le avisa" in salida
    assert "tomas@demo.huella.test: no habilitado" in salida
