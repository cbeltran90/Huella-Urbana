from datetime import timedelta

import pytest
from django.utils import timezone
from model_bakery import baker

from apps.cuentas.models import EstadoCuenta, Sancion, Usuario
from apps.fichas.models import FichaAnimal
from apps.transito import postulaciones, servicios
from apps.transito.models import Alojamiento, PerfilTransito, Postulacion
from apps.transito.postulaciones import ContactoInvalido, PostulacionNoPermitida

CLAVE = "clave-de-prueba-1"
Estado = FichaAnimal.Estado

pytestmark = pytest.mark.django_db


def crear_hogar(nombre, **perfil):
    usuario = Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    datos = {
        "especies_aceptadas": "perro",
        "tamano_maximo": "mediano",
        "duracion_maxima_dias": 30,
        "cupo_declarado": 2,
        **perfil,
    }
    PerfilTransito.objects.create(usuario=usuario, **datos)
    return usuario


def crear_ficha(**campos):
    datos = {"especie": "perro", "tamano": "mediano", "estado": Estado.EN_ADOPCION, **campos}
    return FichaAnimal.objects.create(**datos)


def motivo(usuario, ficha):
    resultado = postulaciones.motivo_para_no_postularse(usuario, ficha)
    return resultado[0] if resultado else None


def sancionar(usuario):
    return Sancion.objects.create(
        usuario=usuario,
        email_hash=usuario.email_hash,
        tipo=Sancion.Tipo.TEMPORAL,
        motivo="Motivo de prueba",
        fin=timezone.now() + timedelta(days=3),
    )


@pytest.fixture
def lucia():
    return crear_hogar("lucia")


def test_un_hogar_habilitado_se_postula_y_queda_pendiente(lucia):
    ficha = crear_ficha()

    postulacion = postulaciones.postular_transito(lucia, ficha, "  2901-555555  ")

    assert postulacion.ficha == ficha
    assert postulacion.usuario == lucia
    assert postulacion.tipo == Postulacion.Tipo.TRANSITO
    assert postulacion.estado == Postulacion.Estado.PENDIENTE
    assert postulacion.contacto == "2901-555555"


def test_varios_hogares_pueden_postularse_a_la_misma_ficha(lucia):
    ficha = crear_ficha()
    postulaciones.postular_transito(lucia, ficha, "2901-111111")
    postulaciones.postular_transito(crear_hogar("martin"), ficha, "2901-222222")
    assert ficha.postulaciones.count() == 2


# 3A: sin perfil, en pausa o suspendido


def test_sin_perfil_de_transito_no_puede_postularse():
    usuario = Usuario.objects.create_user(
        "sin@example.com", "Sin", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    with pytest.raises(PostulacionNoPermitida) as error:
        postulaciones.postular_transito(usuario, crear_ficha(), "2901-555555")
    assert error.value.codigo == "sin_perfil"
    assert error.value.mensaje == postulaciones.MENSAJE_SIN_PERFIL


def test_con_el_perfil_desactivado_no_puede_postularse(lucia):
    PerfilTransito.objects.filter(usuario=lucia).update(activo=False)
    assert motivo(lucia, crear_ficha()) == "sin_perfil"


def test_en_pausa_no_puede_postularse(lucia):
    hasta = timezone.localdate() + timedelta(days=10)
    PerfilTransito.objects.filter(usuario=lucia).update(disponibilidad=False, pausa_hasta=hasta)
    with pytest.raises(PostulacionNoPermitida) as error:
        postulaciones.postular_transito(lucia, crear_ficha(), "2901-555555")
    assert error.value.codigo == "en_pausa"
    assert not Postulacion.objects.exists()


def test_una_pausa_vencida_ya_no_impide_postularse(lucia):
    ayer = timezone.localdate() - timedelta(days=1)
    PerfilTransito.objects.filter(usuario=lucia).update(disponibilidad=False, pausa_hasta=ayer)
    assert motivo(lucia, crear_ficha()) is None


def test_con_la_cuenta_suspendida_no_puede_postularse(lucia):
    sancionar(lucia)
    with pytest.raises(PostulacionNoPermitida) as error:
        postulaciones.postular_transito(lucia, crear_ficha(), "2901-555555")
    assert error.value.codigo == "suspendido"
    assert not Postulacion.objects.exists()


# La ficha tiene que estar en adopción y no estar a cargo del hogar


@pytest.mark.parametrize("estado", [Estado.REGISTRADO, Estado.SIN_RESPONSABLE, Estado.EN_TRANSITO])
def test_solo_se_postula_a_una_ficha_en_adopcion(lucia, estado):
    assert motivo(lucia, crear_ficha(estado=estado)) == "ficha_no_disponible"


def test_no_puede_postularse_para_un_animal_que_tiene_a_su_cargo(lucia):
    assert motivo(lucia, crear_ficha(cuidador=lucia)) == "tiene_el_animal"


def test_no_puede_postularse_para_un_animal_del_que_es_responsable(lucia):
    assert motivo(lucia, crear_ficha(responsable=lucia)) == "tiene_el_animal"


def test_no_puede_postularse_para_un_animal_que_aloja_hoy(lucia):
    ficha = crear_ficha()
    Alojamiento.objects.create(
        ficha=ficha,
        hogar=lucia.perfil_transito,
        fecha_fin_prevista=timezone.localdate() + timedelta(days=30),
    )
    assert motivo(lucia, ficha) == "tiene_el_animal"


def test_un_alojamiento_cerrado_no_impide_postularse(lucia):
    ficha = crear_ficha()
    hoy = timezone.localdate()
    Alojamiento.objects.create(
        ficha=ficha,
        hogar=lucia.perfil_transito,
        fecha_fin_prevista=hoy,
        fecha_fin_real=hoy,
        motivo_fin=Alojamiento.MotivoFin.RELEVO,
    )
    assert motivo(lucia, ficha) is None


# 3C: ya tiene una postulación activa


def crear_postulacion(usuario, ficha, estado):
    return baker.make(
        Postulacion,
        ficha=ficha,
        usuario=usuario,
        tipo=Postulacion.Tipo.TRANSITO,
        contacto="2901-555555",
        estado=estado,
    )


def test_no_puede_postularse_dos_veces_a_la_misma_ficha(lucia):
    ficha = crear_ficha()
    postulaciones.postular_transito(lucia, ficha, "2901-555555")
    with pytest.raises(PostulacionNoPermitida) as error:
        postulaciones.postular_transito(lucia, ficha, "2901-555555")
    assert error.value.codigo == "ya_postulado"
    assert ficha.postulaciones.count() == 1


def test_una_postulacion_elegida_tambien_impide_postularse_de_nuevo(lucia):
    ficha = crear_ficha()
    crear_postulacion(lucia, ficha, Postulacion.Estado.ELEGIDA)
    assert motivo(lucia, ficha) == "ya_postulado"


def test_puede_volver_a_postularse_si_la_anterior_fue_descartada(lucia):
    ficha = crear_ficha()
    crear_postulacion(lucia, ficha, Postulacion.Estado.DESCARTADA)
    postulaciones.postular_transito(lucia, ficha, "2901-555555")
    assert ficha.postulaciones.filter(estado=Postulacion.Estado.PENDIENTE).count() == 1


def test_puede_volver_a_postularse_si_la_anterior_fue_concretada(lucia):
    ficha = crear_ficha()
    crear_postulacion(lucia, ficha, Postulacion.Estado.CONCRETADA)
    assert motivo(lucia, ficha) is None


def test_si_la_base_rechaza_una_segunda_postulacion_se_informa_como_ya_postulado(
    lucia, monkeypatch
):
    ficha = crear_ficha()
    postulaciones.postular_transito(lucia, ficha, "2901-555555")
    monkeypatch.setattr(postulaciones, "motivo_para_no_postularse", lambda *args: None)
    with pytest.raises(PostulacionNoPermitida) as error:
        postulaciones.postular_transito(lucia, ficha, "2901-555555")
    assert error.value.codigo == "ya_postulado"


# Cupo e incompatibilidad no impiden postularse


def test_un_hogar_con_el_cupo_completo_puede_postularse():
    hogar = crear_hogar("beto", cupo_declarado=1)
    Alojamiento.objects.create(
        ficha=crear_ficha(estado=Estado.EN_TRANSITO),
        hogar=hogar.perfil_transito,
        fecha_fin_prevista=timezone.localdate() + timedelta(days=30),
    )
    postulaciones.postular_transito(hogar, crear_ficha(), "2901-555555")
    assert Postulacion.objects.filter(usuario=hogar).count() == 1


def test_un_hogar_no_compatible_puede_postularse_y_recibe_la_advertencia(lucia):
    ficha = crear_ficha(tamano="grande", requiere_medicacion=True)

    postulaciones.postular_transito(lucia, ficha, "2901-555555")

    assert postulaciones.advertencias_de_postulacion(lucia, ficha) == [
        servicios.MOTIVO_TAMANO,
        servicios.MOTIVO_MEDICACION,
    ]


def test_un_hogar_compatible_no_tiene_advertencias(lucia):
    assert postulaciones.advertencias_de_postulacion(lucia, crear_ficha()) == []


def test_sin_perfil_no_hay_advertencias():
    usuario = Usuario.objects.create_user(
        "sin@example.com", "Sin", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    assert postulaciones.advertencias_de_postulacion(usuario, crear_ficha()) == []


# Canal de contacto


@pytest.mark.parametrize("contacto", ["", "   ", None])
def test_el_canal_de_contacto_es_obligatorio(lucia, contacto):
    with pytest.raises(ContactoInvalido) as error:
        postulaciones.postular_transito(lucia, crear_ficha(), contacto)
    assert str(error.value) == postulaciones.MENSAJE_CONTACTO_VACIO
    assert not Postulacion.objects.exists()


def test_el_canal_de_contacto_no_puede_ser_demasiado_largo(lucia):
    largo = "x" * (postulaciones.CONTACTO_MAXIMO + 1)
    with pytest.raises(ContactoInvalido) as error:
        postulaciones.postular_transito(lucia, crear_ficha(), largo)
    assert str(error.value) == postulaciones.MENSAJE_CONTACTO_LARGO
    assert not Postulacion.objects.exists()
