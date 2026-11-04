import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.cuentas.models import EstadoCuenta, Rol, Usuario

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"


@pytest.fixture
def root(client):
    usuario = Usuario.objects.create_superuser("root@example.com", "Root", CLAVE)
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


@pytest.fixture
def moderador(client):
    usuario = Usuario.objects.create_user(
        "mod@example.com", "Moderadora", CLAVE, rol=Rol.MODERADOR, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def cambiar(client, usuario, **cambios):
    """Envía el formulario de edición del panel con los datos actuales y los cambios pedidos."""
    datos = {
        "email": usuario.email,
        "nombre_usuario": usuario.nombre_usuario,
        "first_name": "",
        "last_name": "",
        "rol": usuario.rol,
        "estado_cuenta": usuario.estado_cuenta,
        "_save": "Guardar",
        **cambios,
    }
    return client.post(reverse("admin:cuentas_usuario_change", args=[usuario.pk]), datos)


@pytest.mark.django_db
def test_el_administrador_cambia_el_rol_de_un_usuario(client, root, ana):
    respuesta = cambiar(client, ana, rol=Rol.MODERADOR)

    assert respuesta.status_code == 302
    ana.refresh_from_db()
    assert ana.rol == Rol.MODERADOR
    assert ana.is_staff
    assert not ana.is_superuser


@pytest.mark.django_db
def test_el_administrador_marca_una_cuenta_como_organizacion(client, root, ana):
    respuesta = cambiar(client, ana, es_organizacion="on")

    assert respuesta.status_code == 302
    ana.refresh_from_db()
    assert ana.es_organizacion


@pytest.mark.django_db
def test_el_cambio_de_rol_queda_en_el_registro_del_panel(client, root, ana):
    cambiar(client, ana, rol=Rol.MODERADOR)

    entrada = LogEntry.objects.get(
        content_type=ContentType.objects.get_for_model(Usuario), object_id=str(ana.pk)
    )
    assert entrada.user == root
    assert entrada.action_flag == CHANGE
    assert entrada.action_time is not None
    assert "rol" in entrada.get_change_message().lower()


@pytest.mark.django_db
def test_un_moderador_no_puede_cambiar_roles(client, moderador, ana):
    respuesta = cambiar(client, ana, rol=Rol.ADMINISTRADOR)

    assert respuesta.status_code == 403
    ana.refresh_from_db()
    assert ana.rol == Rol.REGISTRADO
    assert not LogEntry.objects.exists()


@pytest.mark.django_db
def test_un_moderador_no_puede_crear_ni_borrar_usuarios(client, moderador, ana):
    assert client.get(reverse("admin:cuentas_usuario_add")).status_code == 403
    borrar = reverse("admin:cuentas_usuario_delete", args=[ana.pk])
    assert client.post(borrar, {"post": "yes"}).status_code == 403
    assert Usuario.objects.filter(pk=ana.pk).exists()


@pytest.mark.django_db
def test_el_administrador_no_cambia_su_propio_rol(client, root):
    cambiar(client, root, rol=Rol.REGISTRADO, estado_cuenta=EstadoCuenta.PENDIENTE)

    root.refresh_from_db()
    assert root.rol == Rol.ADMINISTRADOR
    assert root.estado_cuenta == EstadoCuenta.ACTIVA
    assert root.is_superuser


@pytest.mark.django_db
def test_el_administrador_no_borra_su_propia_cuenta(client, root):
    borrar = reverse("admin:cuentas_usuario_delete", args=[root.pk])

    assert client.post(borrar, {"post": "yes"}).status_code == 403
    assert Usuario.objects.filter(pk=root.pk).exists()


@pytest.mark.django_db
def test_el_administrador_si_borra_la_cuenta_de_otra_persona(client, root, ana):
    borrar = reverse("admin:cuentas_usuario_delete", args=[ana.pk])

    assert client.post(borrar, {"post": "yes"}).status_code == 302
    assert not Usuario.objects.filter(pk=ana.pk).exists()


@pytest.mark.django_db
def test_se_busca_un_usuario_por_correo_y_por_nombre(client, root, ana):
    Usuario.objects.create_user("beto@example.com", "Beto", CLAVE)
    lista = reverse("admin:cuentas_usuario_changelist")

    por_correo = client.get(lista, {"q": "ana@example"}).content.decode()
    assert "ana@example.com" in por_correo
    assert "beto@example.com" not in por_correo

    por_nombre = client.get(lista, {"q": "Beto"}).content.decode()
    assert "beto@example.com" in por_nombre
    assert "ana@example.com" not in por_nombre


@pytest.mark.django_db
def test_si_la_busqueda_no_encuentra_a_nadie_avisa(client, root, ana):
    lista = reverse("admin:cuentas_usuario_changelist")

    sin_resultados = client.get(lista, {"q": "nadie-con-este-nombre"})
    assert "No se encontró ningún usuario" in sin_resultados.content.decode()

    con_resultados = client.get(lista, {"q": "ana"})
    assert "No se encontró ningún usuario" not in con_resultados.content.decode()
