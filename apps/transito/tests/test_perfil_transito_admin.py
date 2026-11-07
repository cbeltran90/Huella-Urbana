import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.cuentas.models import EstadoCuenta, Rol, Usuario
from apps.transito import servicios
from apps.transito.models import PerfilTransito

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"


def lista():
    return reverse("admin:transito_perfiltransito_changelist")


@pytest.fixture
def moderador(client):
    usuario = Usuario.objects.create_user(
        "mod@example.com", "Moderadora", CLAVE, rol=Rol.MODERADOR, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


@pytest.fixture
def administrador(client):
    usuario = Usuario.objects.create_superuser("root@example.com", "Root", CLAVE)
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


def hogar(nombre, **campos):
    usuario = Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    datos = {
        "especies_aceptadas": "perro",
        "tamano_maximo": "mediano",
        "duracion_maxima_dias": 30,
        "cupo_declarado": 2,
        **campos,
    }
    return PerfilTransito.objects.create(usuario=usuario, **datos)


def elegir_accion(client, *perfiles):
    """Lo que envía la lista al elegir la acción: pide la confirmación."""
    datos = {
        "action": "retirar_rol",
        "_selected_action": [perfil.pk for perfil in perfiles],
        "index": "0",
    }
    return client.post(lista(), datos)


def confirmar_accion(client, *perfiles, **extra):
    """Lo que envía la pantalla de confirmación (sin "index")."""
    datos = {
        "action": "retirar_rol",
        "_selected_action": [perfil.pk for perfil in perfiles],
        "confirmar": "1",
    }
    return client.post(lista(), datos, **extra)


def registros_de(usuario):
    return LogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(Usuario), object_id=str(usuario.pk)
    )


# Quién ve la sección


@pytest.mark.django_db
def test_el_moderador_ve_la_lista_de_perfiles(client, moderador):
    hogar("ana")

    respuesta = client.get(lista())

    assert respuesta.status_code == 200
    assert "Ana" in respuesta.content.decode()


@pytest.mark.django_db
def test_el_administrador_ve_la_lista_de_perfiles(client, administrador):
    hogar("ana")

    assert client.get(lista()).status_code == 200


@pytest.mark.django_db
def test_una_persona_registrada_no_entra_al_panel(client):
    registrada = Usuario.objects.create_user(
        "reg@example.com", "Reg", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(registrada, backend=BACKEND_MODELO)

    respuesta = client.get(lista())

    assert respuesta.status_code == 302
    assert "login" in respuesta["Location"]


@pytest.mark.django_db
def test_se_busca_por_correo_y_por_nombre(client, moderador):
    hogar("ana")
    hogar("beto")

    por_correo = client.get(lista(), {"q": "ana@example.com"}).content.decode()
    por_nombre = client.get(lista(), {"q": "Beto"}).content.decode()

    assert "ana@example.com" in por_correo or "Ana" in por_correo
    assert "Beto" not in por_correo
    assert "Beto" in por_nombre
    assert "Ana" not in por_nombre


@pytest.mark.django_db
def test_la_lista_se_puede_filtrar_por_activos(client, moderador):
    hogar("ana")
    hogar("beto", activo=False)

    contenido = client.get(lista(), {"activo__exact": "1"}).content.decode()

    assert "Ana" in contenido
    assert "Beto" not in contenido


@pytest.mark.django_db
@pytest.mark.parametrize("quien", ["moderador", "administrador"])
def test_nadie_crea_edita_ni_borra_perfiles_desde_el_panel(client, request, quien):
    request.getfixturevalue(quien)
    perfil = hogar("ana")

    assert client.get(reverse("admin:transito_perfiltransito_add")).status_code == 403
    borrar = reverse("admin:transito_perfiltransito_delete", args=[perfil.pk])
    assert client.post(borrar, {"post": "yes"}).status_code == 403
    cambiar = reverse("admin:transito_perfiltransito_change", args=[perfil.pk])
    assert client.post(cambiar, {"cupo_declarado": 9}).status_code == 403
    perfil.refresh_from_db()
    assert perfil.cupo_declarado == 2


@pytest.mark.django_db
def test_la_lista_ofrece_la_accion_de_retirar_el_rol(client, moderador):
    hogar("ana")

    contenido = client.get(lista()).content.decode()

    assert "Retirar el rol de hogar de tránsito" in contenido


# Retirar el rol: confirmar o cancelar


@pytest.mark.django_db
def test_elegir_la_accion_pide_confirmar_y_no_cambia_nada(client, moderador):
    perfil = hogar("ana")

    respuesta = elegir_accion(client, perfil)

    contenido = respuesta.content.decode()
    assert respuesta.status_code == 200
    assert "¿Seguro que querés retirar el rol de hogar de tránsito" in contenido
    assert "ana@example.com" in contenido
    assert "Cancelar" in contenido
    assert lista() in contenido
    perfil.refresh_from_db()
    assert perfil.activo is True
    assert not registros_de(perfil.usuario).exists()


@pytest.mark.django_db
def test_confirmar_retira_el_rol_y_deja_constancia(client, moderador):
    perfil = hogar("ana")

    respuesta = confirmar_accion(client, perfil)

    assert respuesta.status_code == 302
    perfil.refresh_from_db()
    assert perfil.activo is False
    assert servicios.es_hogar_de_transito(perfil.usuario) is False
    entrada = registros_de(perfil.usuario).get()
    assert entrada.user == moderador


@pytest.mark.django_db
def test_el_administrador_tambien_confirma_el_retiro(client, administrador):
    perfil = hogar("ana")

    confirmar_accion(client, perfil)

    perfil.refresh_from_db()
    assert perfil.activo is False


@pytest.mark.django_db
def test_confirmar_avisa_cuantos_roles_se_retiraron(client, moderador):
    ana = hogar("ana")
    beto = hogar("beto")

    respuesta = confirmar_accion(client, ana, beto, follow=True)

    mensajes = [str(mensaje) for mensaje in respuesta.context["messages"]]
    assert "Roles de hogar de tránsito retirados: 2." in mensajes


@pytest.mark.django_db
def test_con_animales_a_cargo_no_se_retira_y_el_panel_lo_avisa(client, moderador, monkeypatch):
    perfil = hogar("ana")
    monkeypatch.setattr(servicios, "tiene_animales_a_cargo", lambda usuario: True)

    respuesta = confirmar_accion(client, perfil, follow=True)

    mensajes = [str(mensaje) for mensaje in respuesta.context["messages"]]
    assert any("tiene animales a su cargo" in mensaje for mensaje in mensajes)
    perfil.refresh_from_db()
    assert perfil.activo is True
    assert not registros_de(perfil.usuario).exists()


@pytest.mark.django_db
def test_un_perfil_ya_desactivado_se_avisa_y_no_se_registra_de_nuevo(client, moderador):
    perfil = hogar("ana", activo=False)

    respuesta = confirmar_accion(client, perfil, follow=True)

    mensajes = [str(mensaje) for mensaje in respuesta.context["messages"]]
    assert any("No hay un perfil de tránsito activo" in mensaje for mensaje in mensajes)
    assert not registros_de(perfil.usuario).exists()


@pytest.mark.django_db
def test_una_persona_registrada_no_puede_usar_la_accion(client):
    registrada = Usuario.objects.create_user(
        "reg@example.com", "Reg", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    client.force_login(registrada, backend=BACKEND_MODELO)
    perfil = hogar("ana")

    confirmar_accion(client, perfil)

    perfil.refresh_from_db()
    assert perfil.activo is True
