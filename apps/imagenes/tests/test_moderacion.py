import pytest
from django.contrib.admin.models import LogEntry

from apps.cuentas.models import EstadoCuenta, Rol, Usuario
from apps.imagenes import moderacion
from apps.imagenes.models import Fotografia

pytestmark = pytest.mark.django_db

CLAVE = "clave-de-prueba-1"


def foto(motivo=Fotografia.MotivoRevision.SIN_ANIMAL):
    return Fotografia.objects.create(archivo="x.jpg", hash_sha256="a" * 64, motivo_revision=motivo)


@pytest.fixture
def moderador():
    return Usuario.objects.create_user(
        "mod@example.com", "Mod", CLAVE, rol=Rol.MODERADOR, estado_cuenta=EstadoCuenta.ACTIVA
    )


def test_la_foto_queda_revisada_y_sin_marca(moderador):
    fotografia = foto()

    assert moderacion.marcar_revisada(fotografia, moderador) is True

    fotografia.refresh_from_db()
    assert fotografia.revisada_por == moderador
    assert fotografia.motivo_revision == ""


def test_queda_constancia_con_el_motivo_de_la_marca(moderador):
    fotografia = foto(Fotografia.MotivoRevision.DUPLICADA)

    moderacion.marcar_revisada(fotografia, moderador)

    entrada = LogEntry.objects.get(object_id=str(fotografia.pk))
    assert entrada.user == moderador
    assert "Duplicada" in entrada.change_message


def test_una_foto_sin_marca_no_cambia(moderador):
    fotografia = foto(motivo="")

    assert moderacion.marcar_revisada(fotografia, moderador) is False

    fotografia.refresh_from_db()
    assert fotografia.revisada_por is None
    assert not LogEntry.objects.exists()


def test_un_usuario_comun_no_puede_revisar(ana):
    fotografia = foto()

    with pytest.raises(PermissionError):
        moderacion.marcar_revisada(fotografia, ana)

    fotografia.refresh_from_db()
    assert fotografia.motivo_revision == Fotografia.MotivoRevision.SIN_ANIMAL
    assert fotografia.revisada_por is None
