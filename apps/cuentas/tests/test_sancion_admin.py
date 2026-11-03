from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.cuentas.models import EstadoCuenta, Sancion, Usuario

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"


@pytest.fixture
def root(client):
    usuario = Usuario.objects.create_superuser("root@example.com", "Root", CLAVE)
    client.force_login(usuario, backend=BACKEND_MODELO)
    return usuario


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


@pytest.fixture
def sancion_de_ana(ana, root):
    return Sancion.objects.create(
        usuario=ana,
        email_hash=ana.email_hash,
        tipo=Sancion.Tipo.PERMANENTE,
        motivo="Motivo de prueba",
        aplicada_por=root,
    )


def alta(client, **datos):
    return client.post(reverse("admin:cuentas_sancion_add"), {"_save": "Guardar", **datos})


@pytest.mark.django_db
def test_se_carga_una_sancion_temporal_desde_el_panel(client, root, ana):
    respuesta = alta(client, usuario=ana.pk, tipo="temporal", motivo="Publicó contenido ofensivo")

    assert respuesta.status_code == 302
    sancion = Sancion.objects.get()
    assert sancion.usuario == ana
    assert sancion.aplicada_por == root
    assert sancion.email_hash == ana.email_hash
    assert abs(sancion.fin - (timezone.now() + timedelta(days=7))) < timedelta(minutes=1)


@pytest.mark.django_db
def test_el_panel_no_deja_sancionar_la_propia_cuenta(client, root):
    respuesta = alta(client, usuario=root.pk, tipo="temporal", motivo="Motivo")
    assert respuesta.status_code == 200
    assert "No podés sancionar tu propia cuenta" in respuesta.content.decode()
    assert not Sancion.objects.exists()


@pytest.mark.django_db
def test_el_panel_exige_el_motivo(client, root, ana):
    respuesta = alta(client, usuario=ana.pk, tipo="temporal", motivo="")
    assert respuesta.status_code == 200
    assert not Sancion.objects.exists()


@pytest.mark.django_db
def test_el_panel_no_deja_sancionar_dos_veces(client, root, ana, sancion_de_ana):
    respuesta = alta(client, usuario=ana.pk, tipo="temporal", motivo="Otro motivo")
    assert respuesta.status_code == 200
    assert "ya tiene una sanción vigente" in respuesta.content.decode()
    assert Sancion.objects.count() == 1


@pytest.mark.django_db
def test_la_lista_y_el_detalle_cargan(client, root, sancion_de_ana):
    lista = client.get(reverse("admin:cuentas_sancion_changelist"))
    detalle = client.get(reverse("admin:cuentas_sancion_change", args=[sancion_de_ana.pk]))
    assert lista.status_code == 200
    assert "Ana" in lista.content.decode()
    assert detalle.status_code == 200


@pytest.mark.django_db
def test_una_sancion_no_se_edita_ni_se_borra(client, root, sancion_de_ana):
    cambiar = reverse("admin:cuentas_sancion_change", args=[sancion_de_ana.pk])
    borrar = reverse("admin:cuentas_sancion_delete", args=[sancion_de_ana.pk])
    assert client.post(cambiar, {"motivo": "Otro"}).status_code == 403
    assert client.get(borrar).status_code == 403


@pytest.mark.django_db
def test_la_accion_levanta_la_sancion(client, root, ana, sancion_de_ana):
    respuesta = client.post(
        reverse("admin:cuentas_sancion_changelist"),
        {"action": "levantar", "_selected_action": [sancion_de_ana.pk]},
    )
    assert respuesta.status_code == 302
    sancion_de_ana.refresh_from_db()
    assert sancion_de_ana.revocada_en is not None
    assert sancion_de_ana.revocada_por == root
