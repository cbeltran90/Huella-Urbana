import pytest
from django.contrib.admin.models import LogEntry

from apps.cuentas.models import EstadoCuenta, Rol, Usuario
from apps.publicaciones import moderacion
from apps.publicaciones.models import Publicacion

from .conftest import hacer_publicacion

pytestmark = pytest.mark.django_db

CLAVE = "clave-de-prueba-1"


def cuenta(correo, rol):
    return Usuario.objects.create_user(
        correo, correo.split("@")[0].title(), CLAVE, rol=rol, estado_cuenta=EstadoCuenta.ACTIVA
    )


@pytest.fixture
def moderador():
    return cuenta("mod@example.com", Rol.MODERADOR)


def test_la_publicacion_queda_eliminada_con_su_fecha(ana, moderador):
    publicacion = hacer_publicacion(ana)

    assert moderacion.eliminar_publicacion(publicacion, moderador) is True

    publicacion.refresh_from_db()
    assert publicacion.estado == Publicacion.Estado.ELIMINADA
    assert publicacion.fecha_eliminacion is not None


def test_se_conservan_sus_datos(ana, moderador):
    publicacion = hacer_publicacion(ana, descripcion="Se perdió cerca del puerto")

    moderacion.eliminar_publicacion(publicacion, moderador)

    publicacion.refresh_from_db()
    assert publicacion.descripcion == "Se perdió cerca del puerto"
    assert publicacion.autor == ana


def test_queda_constancia_en_el_registro_de_acciones(ana, moderador):
    publicacion = hacer_publicacion(ana)

    moderacion.eliminar_publicacion(publicacion, moderador)

    entrada = LogEntry.objects.get(object_id=str(publicacion.pk))
    assert entrada.user == moderador


def test_si_ya_estaba_eliminada_no_hace_nada(ana, moderador):
    publicacion = hacer_publicacion(ana)
    moderacion.eliminar_publicacion(publicacion, moderador)

    assert moderacion.eliminar_publicacion(publicacion, moderador) is False

    assert LogEntry.objects.filter(object_id=str(publicacion.pk)).count() == 1


def test_un_usuario_comun_no_puede_eliminar(ana, beto):
    publicacion = hacer_publicacion(ana)

    with pytest.raises(PermissionError):
        moderacion.eliminar_publicacion(publicacion, beto)

    publicacion.refresh_from_db()
    assert publicacion.estado == Publicacion.Estado.VIGENTE
