import pytest
from django.urls import reverse

from apps.cuentas.models import EstadoCuenta, Rol, Sancion, Usuario

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"


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


@pytest.fixture
def administrador():
    return Usuario.objects.create_superuser("root@example.com", "Root", CLAVE)


@pytest.fixture
def sancion_de_ana(ana, administrador):
    return Sancion.objects.create(
        usuario=ana,
        email_hash=ana.email_hash,
        tipo=Sancion.Tipo.PERMANENTE,
        motivo="Motivo de prueba",
        aplicada_por=administrador,
    )


def cargar_sancion(client, usuario):
    return client.post(
        reverse("admin:cuentas_sancion_add"),
        {"usuario": usuario.pk, "tipo": "temporal", "motivo": "Publicó contenido ofensivo"},
    )


@pytest.mark.django_db
def test_un_registrado_no_entra_al_panel(client, ana):
    client.force_login(ana, backend=BACKEND_MODELO)
    respuesta = client.get(reverse("admin:cuentas_usuario_changelist"))
    assert respuesta.status_code == 302
    assert "login" in respuesta["Location"]


@pytest.mark.django_db
def test_el_moderador_ve_el_listado_de_usuarios(client, moderador, ana):
    respuesta = client.get(reverse("admin:cuentas_usuario_changelist"))
    assert respuesta.status_code == 200
    assert "ana@example.com" in respuesta.content.decode()


@pytest.mark.django_db
def test_el_moderador_ve_la_ficha_solo_con_datos_basicos(client, moderador, ana):
    respuesta = client.get(reverse("admin:cuentas_usuario_change", args=[ana.pk]))
    contenido = respuesta.content.decode()

    assert respuesta.status_code == 200
    assert "ana@example.com" in contenido
    assert "pbkdf2_sha256" not in contenido
    assert 'name="user_permissions"' not in contenido
    assert 'name="rol"' not in contenido
    assert 'name="_save"' not in contenido


@pytest.mark.django_db
def test_el_moderador_no_cambia_la_contrasena_de_otra_cuenta(client, moderador, ana):
    url = reverse("admin:auth_user_password_change", args=[ana.pk])
    assert client.get(url).status_code == 403


@pytest.mark.django_db
def test_el_moderador_carga_una_sancion(client, moderador, ana):
    respuesta = cargar_sancion(client, ana)

    assert respuesta.status_code == 302
    sancion = Sancion.objects.get()
    assert sancion.usuario == ana
    assert sancion.aplicada_por == moderador


@pytest.mark.django_db
def test_el_moderador_no_sanciona_a_un_administrador(client, moderador, administrador):
    respuesta = cargar_sancion(client, administrador)

    assert respuesta.status_code == 200
    assert not Sancion.objects.exists()


@pytest.mark.django_db
def test_el_moderador_levanta_una_sancion(client, moderador, sancion_de_ana):
    respuesta = client.post(
        reverse("admin:cuentas_sancion_changelist"),
        {"action": "levantar", "_selected_action": [sancion_de_ana.pk]},
    )

    assert respuesta.status_code == 302
    sancion_de_ana.refresh_from_db()
    assert sancion_de_ana.revocada_en is not None
    assert sancion_de_ana.revocada_por == moderador


@pytest.mark.django_db
def test_el_moderador_no_edita_una_sancion_existente(client, moderador, sancion_de_ana):
    url = reverse("admin:cuentas_sancion_change", args=[sancion_de_ana.pk])
    assert client.post(url, {"motivo": "Otro motivo"}).status_code == 403
    sancion_de_ana.refresh_from_db()
    assert sancion_de_ana.motivo == "Motivo de prueba"


@pytest.mark.django_db
def test_el_buscador_de_usuarios_de_sanciones_funciona_para_el_moderador(client, moderador, ana):
    respuesta = client.get(
        reverse("admin:autocomplete"),
        {"term": "ana", "app_label": "cuentas", "model_name": "sancion", "field_name": "usuario"},
    )

    assert respuesta.status_code == 200
    assert "ana@example.com" in respuesta.content.decode() or "Ana" in respuesta.content.decode()
