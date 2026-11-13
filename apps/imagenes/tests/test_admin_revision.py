import pytest
from django.urls import reverse

from apps.cuentas.models import EstadoCuenta, Rol, Usuario
from apps.imagenes.models import Fotografia

pytestmark = pytest.mark.django_db

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"
ACCION = "marcar_revisada"


def lista():
    return reverse("admin:imagenes_fotografia_changelist")


def entrar_como(client, rol):
    usuario = Usuario.objects.create_user(
        "mod@example.com", "Mod", CLAVE, rol=rol, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


def foto(motivo=Fotografia.MotivoRevision.SIN_ANIMAL):
    return Fotografia.objects.create(archivo="x.jpg", hash_sha256="a" * 64, motivo_revision=motivo)


def revisar(client, *fotos):
    return client.post(lista(), {"action": ACCION, "_selected_action": [f.pk for f in fotos]})


@pytest.mark.parametrize("rol", [Rol.MODERADOR, Rol.ADMINISTRADOR])
def test_moderadores_y_administradores_ven_el_listado(client, rol):
    entrar_como(client, rol)
    foto()

    assert client.get(lista()).status_code == 200


def test_el_filtro_de_pendientes_muestra_solo_las_marcadas(client):
    entrar_como(client, Rol.MODERADOR)
    marcada = foto()
    foto(motivo="")

    respuesta = client.get(lista(), {"revision": "pendientes"})

    assert [f.pk for f in respuesta.context["cl"].result_list] == [marcada.pk]


def test_el_filtro_de_revisadas_muestra_solo_las_revisadas(client):
    moderador = entrar_como(client, Rol.MODERADOR)
    revisada = foto(motivo="")
    revisada.revisada_por = moderador
    revisada.save()
    foto()

    respuesta = client.get(lista(), {"revision": "revisadas"})

    assert [f.pk for f in respuesta.context["cl"].result_list] == [revisada.pk]


@pytest.mark.parametrize("rol", [Rol.MODERADOR, Rol.ADMINISTRADOR])
def test_la_accion_marca_revisadas_las_fotos_elegidas(client, rol):
    moderador = entrar_como(client, rol)
    una = foto()
    otra = foto(Fotografia.MotivoRevision.DUPLICADA)
    queda = foto()

    revisar(client, una, otra)

    una.refresh_from_db()
    otra.refresh_from_db()
    queda.refresh_from_db()
    assert una.motivo_revision == "" and una.revisada_por == moderador
    assert otra.motivo_revision == "" and otra.revisada_por == moderador
    assert queda.motivo_revision == Fotografia.MotivoRevision.SIN_ANIMAL


def test_un_usuario_comun_no_entra_ni_revisa(client):
    entrar_como(client, Rol.REGISTRADO)
    fotografia = foto()

    assert client.get(lista()).status_code == 302
    revisar(client, fotografia)

    fotografia.refresh_from_db()
    assert fotografia.motivo_revision == Fotografia.MotivoRevision.SIN_ANIMAL
