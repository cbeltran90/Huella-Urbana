from datetime import timedelta

import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse
from django.utils import timezone

from apps.cuentas import eliminacion
from apps.cuentas.forms import RegistroForm
from apps.cuentas.models import (
    Domicilio,
    EstadoCuenta,
    PerfilAdoptante,
    Rol,
    Sancion,
    Usuario,
    hash_email,
)
from apps.cuentas.servicios import correo_con_suspension_permanente
from apps.fichas.models import FichaAnimal
from apps.transito import servicios as servicios_transito
from apps.transito.models import PerfilTransito

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"
PUNTO = Point(-68.3100, -54.8100, srid=4326)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def sin_pasos_de_otros_modulos(monkeypatch):
    """Cada prueba arranca sin pasos registrados por otros módulos."""
    monkeypatch.setattr(eliminacion, "_LIMPIEZAS", [])


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


@pytest.fixture
def ana_completa(ana):
    Domicilio.objects.create(
        usuario=ana,
        ubicacion=PUNTO,
        ubicacion_desplazada=PUNTO,
        tipo_vivienda="casa",
        tiene_patio=True,
        convivientes=2,
        hay_ninos=False,
        mascotas_propias=1,
    )
    PerfilAdoptante.objects.create(usuario=ana, experiencia_previa="Tuve dos perros.")
    PerfilTransito.objects.create(
        usuario=ana,
        especies_aceptadas="perro,gato",
        tamano_maximo="grande",
        duracion_maxima_dias=30,
        acepta_medicacion=True,
        acepta_conducta=True,
        disponibilidad=True,
        cupo_declarado=3,
    )
    return ana


def sancionar(usuario, tipo, **campos):
    return Sancion.objects.create(
        usuario=usuario,
        email_hash=usuario.email_hash,
        tipo=tipo,
        motivo="Motivo de prueba",
        **campos,
    )


def test_la_cuenta_queda_eliminada_sin_nombre_ni_correo_y_sin_poder_entrar(ana):
    eliminada = eliminacion.eliminar_cuenta(ana)

    ana.refresh_from_db()
    assert eliminada.pk == ana.pk
    assert ana.estado_cuenta == EstadoCuenta.ELIMINADA
    assert ana.email == f"eliminada-{ana.pk}@eliminada.invalid"
    assert ana.nombre_usuario == f"usuario-eliminado-{ana.pk}"
    assert not ana.has_usable_password()
    assert not ana.check_password(CLAVE)
    assert not ana.is_active


def test_el_correo_y_el_nombre_originales_quedan_libres(ana):
    eliminacion.eliminar_cuenta(ana)

    form = RegistroForm(
        {
            "nombre_usuario": "Ana",
            "email": "ana@example.com",
            "password1": CLAVE,
            "password2": CLAVE,
            "acepta_condiciones": "on",
        }
    )

    assert form.is_valid(), form.errors


def test_dos_cuentas_eliminadas_no_chocan_entre_si(ana):
    otra = Usuario.objects.create_user(
        "otra@example.com", "Otra", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )

    eliminacion.eliminar_cuenta(ana)
    eliminacion.eliminar_cuenta(otra)

    assert Usuario.objects.filter(estado_cuenta=EstadoCuenta.ELIMINADA).count() == 2


def test_el_hash_del_correo_no_queda_en_la_cuenta(ana):
    original = hash_email("ana@example.com")

    eliminacion.eliminar_cuenta(ana)

    ana.refresh_from_db()
    assert ana.email_hash != original


def test_se_borran_el_domicilio_y_los_datos_del_hogar(ana_completa):
    eliminacion.eliminar_cuenta(ana_completa)

    assert not Domicilio.objects.filter(usuario=ana_completa).exists()


def test_el_perfil_de_adopcion_conserva_la_fila_sin_datos(ana_completa):
    eliminacion.eliminar_cuenta(ana_completa)

    perfil = PerfilAdoptante.objects.get(usuario=ana_completa)
    assert perfil.experiencia_previa == ""


def test_el_perfil_de_transito_conserva_la_fila_sin_datos_y_sin_rol(ana_completa):
    eliminacion.eliminar_cuenta(ana_completa)

    perfil = PerfilTransito.objects.get(usuario=ana_completa)
    assert perfil.especies_aceptadas == ""
    assert perfil.tamano_maximo == ""
    assert perfil.duracion_maxima_dias == 0
    assert perfil.cupo_declarado == 0
    assert not (perfil.acepta_medicacion or perfil.acepta_conducta or perfil.disponibilidad)
    assert perfil.pausa_hasta is None
    assert not perfil.activo
    ana_completa.refresh_from_db()
    assert not servicios_transito.es_hogar_de_transito(ana_completa)


def test_vaciar_el_perfil_de_transito_sin_perfil_no_falla(ana):
    servicios_transito.vaciar_perfil_transito(ana)
    assert not PerfilTransito.objects.filter(usuario=ana).exists()


def test_se_conservan_las_sanciones_y_el_hash_del_correo_para_la_reincidencia(ana):
    sancion = sancionar(ana, Sancion.Tipo.PERMANENTE)

    eliminacion.eliminar_cuenta(ana)

    sancion.refresh_from_db()
    assert sancion.email_hash == hash_email("ana@example.com")
    assert correo_con_suspension_permanente("ana@example.com")


def test_una_suspension_vencida_tambien_se_conserva(ana):
    sancion = sancionar(
        ana,
        Sancion.Tipo.TEMPORAL,
        inicio=timezone.now() - timedelta(days=8),
        fin=timezone.now() - timedelta(days=1),
    )

    eliminacion.eliminar_cuenta(ana)

    assert Sancion.objects.filter(pk=sancion.pk).exists()


def test_quien_tiene_una_suspension_permanente_puede_eliminar_su_cuenta(ana):
    sancionar(ana, Sancion.Tipo.PERMANENTE)

    eliminacion.eliminar_cuenta(ana)

    ana.refresh_from_db()
    assert ana.estado_cuenta == EstadoCuenta.ELIMINADA


@pytest.mark.parametrize("rol", [Rol.MODERADOR, Rol.ADMINISTRADOR])
def test_la_cuenta_eliminada_pierde_el_rol(rol):
    usuario = Usuario.objects.create_user(
        "mod@example.com", "Mod", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, rol=rol
    )

    eliminacion.eliminar_cuenta(usuario)

    usuario.refresh_from_db()
    assert usuario.rol == Rol.REGISTRADO
    assert not usuario.is_staff
    assert not usuario.is_superuser


def test_una_sesion_abierta_deja_de_valer(client, ana):
    client.force_login(ana, backend=BACKEND_MODELO)

    eliminacion.eliminar_cuenta(ana)

    respuesta = client.get(reverse("cuentas:perfil"))
    assert respuesta.status_code == 302
    assert respuesta.url.startswith(reverse("cuentas:login"))


def test_con_impedimentos_no_cambia_nada(ana_completa):
    sancionar(ana_completa, Sancion.Tipo.TEMPORAL, fin=timezone.now() + timedelta(days=3))
    FichaAnimal.objects.create(
        especie="perro", estado=FichaAnimal.Estado.EN_ADOPCION, responsable=ana_completa
    )

    with pytest.raises(eliminacion.EliminacionNoPermitida) as error:
        eliminacion.eliminar_cuenta(ana_completa)

    assert [i.codigo for i in error.value.impedimentos] == [
        "suspension_temporal",
        "fichas_en_circuito",
    ]
    ana_completa.refresh_from_db()
    assert ana_completa.estado_cuenta == EstadoCuenta.ACTIVA
    assert ana_completa.email == "ana@example.com"
    assert Domicilio.objects.filter(usuario=ana_completa).exists()
    assert PerfilTransito.objects.get(usuario=ana_completa).activo


def test_las_fichas_registradas_no_impiden_eliminar(ana):
    FichaAnimal.objects.create(
        especie="gato", estado=FichaAnimal.Estado.REGISTRADO, responsable=ana
    )

    eliminacion.eliminar_cuenta(ana)

    ana.refresh_from_db()
    assert ana.estado_cuenta == EstadoCuenta.ELIMINADA


def test_eliminar_una_cuenta_ya_eliminada_no_hace_nada(ana):
    eliminacion.eliminar_cuenta(ana)
    ana.refresh_from_db()
    correo = ana.email

    eliminacion.eliminar_cuenta(ana)

    ana.refresh_from_db()
    assert ana.estado_cuenta == EstadoCuenta.ELIMINADA
    assert ana.email == correo


def test_los_pasos_de_otros_modulos_corren_con_la_cuenta_que_se_elimina(ana):
    recibidas = []

    @eliminacion.al_eliminar_cuenta
    def paso(usuario):
        recibidas.append((usuario.pk, usuario.estado_cuenta))

    eliminacion.eliminar_cuenta(ana)

    assert recibidas == [(ana.pk, EstadoCuenta.ACTIVA)]


def test_si_falla_un_paso_de_otro_modulo_no_se_elimina_nada(ana_completa):
    @eliminacion.al_eliminar_cuenta
    def paso_que_falla(usuario):
        raise RuntimeError("falla de prueba")

    with pytest.raises(RuntimeError):
        eliminacion.eliminar_cuenta(ana_completa)

    ana_completa.refresh_from_db()
    assert ana_completa.estado_cuenta == EstadoCuenta.ACTIVA
    assert ana_completa.email == "ana@example.com"
    assert Domicilio.objects.filter(usuario=ana_completa).exists()
    assert PerfilAdoptante.objects.get(usuario=ana_completa).experiencia_previa
