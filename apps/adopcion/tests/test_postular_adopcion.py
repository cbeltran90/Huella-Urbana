import pytest
from django.contrib.gis.geos import Point
from model_bakery import baker

from apps.adopcion import postulaciones
from apps.cuentas import servicios as cuentas
from apps.cuentas.models import Domicilio, Rol, Sancion
from apps.fichas.models import FichaAnimal
from apps.transito.models import Alojamiento, PerfilTransito, Postulacion

Estado = FichaAnimal.Estado

pytestmark = pytest.mark.django_db

PUNTO = Point(-68.3030, -54.8019, srid=4326)
HOGAR = {
    "tipo_vivienda": "casa",
    "tiene_patio": True,
    "convivientes": 2,
    "hay_ninos": False,
    "mascotas_propias": 0,
}


def con_perfil(usuario):
    Domicilio.objects.create(usuario=usuario, ubicacion=PUNTO, ubicacion_desplazada=PUNTO, **HOGAR)
    cuentas.guardar_perfil_adoptante(usuario, "Tuve perros toda la vida.")
    return usuario


def hacer_ficha(estado=Estado.EN_ADOPCION, **campos):
    return baker.make(FichaAnimal, estado=estado, especie="perro", **campos)


def codigo(usuario, ficha):
    motivo = postulaciones.motivo_para_no_postularse(usuario, ficha)
    return motivo and motivo[0]


@pytest.mark.parametrize("estado", [Estado.EN_ADOPCION, Estado.EN_TRANSITO])
def test_puede_postularse_a_un_animal_disponible(ana, estado):
    assert postulaciones.motivo_para_no_postularse(con_perfil(ana), hacer_ficha(estado)) is None


@pytest.mark.parametrize("estado", [Estado.REGISTRADO, Estado.SIN_RESPONSABLE])
def test_no_puede_si_el_animal_no_esta_disponible(ana, estado):
    assert codigo(con_perfil(ana), hacer_ficha(estado)) == "ficha_no_disponible"


def test_sin_perfil_de_hogar_y_familia_no_puede(ana):
    assert codigo(ana, hacer_ficha()) == "perfil_incompleto"


def test_una_cuenta_suspendida_no_puede(ana, beto):
    beto.rol = Rol.MODERADOR
    beto.save()
    cuentas.sancionar(con_perfil(ana), Sancion.Tipo.PERMANENTE, "Motivo", beto)

    assert codigo(ana, hacer_ficha()) == "suspendido"


def test_quien_lo_tiene_a_cargo_puede_postularse_para_quedarselo(ana):
    assert (
        postulaciones.motivo_para_no_postularse(con_perfil(ana), hacer_ficha(cuidador=ana)) is None
    )


def test_el_hogar_que_lo_aloja_puede_postularse_para_quedarselo(ana):
    ficha = hacer_ficha(Estado.EN_TRANSITO)
    perfil = baker.make(PerfilTransito, usuario=con_perfil(ana))
    baker.make(Alojamiento, ficha=ficha, hogar=perfil, fecha_fin_real=None)

    assert postulaciones.motivo_para_no_postularse(ana, ficha) is None


def test_el_responsable_no_puede_adoptar_su_propio_animal(ana):
    assert codigo(con_perfil(ana), hacer_ficha(responsable=ana)) == "es_responsable"


@pytest.mark.parametrize("tipo", [Postulacion.Tipo.ADOPCION, Postulacion.Tipo.TRANSITO])
def test_con_una_postulacion_activa_de_cualquier_tipo_no_puede(ana, tipo):
    ficha = hacer_ficha()
    baker.make(Postulacion, ficha=ficha, usuario=con_perfil(ana), tipo=tipo, contacto="2901 444444")

    assert codigo(ana, ficha) == "ya_postulado"


def test_una_postulacion_retirada_no_impide_volver_a_postularse(ana):
    ficha = hacer_ficha()
    baker.make(
        Postulacion,
        ficha=ficha,
        usuario=con_perfil(ana),
        tipo=Postulacion.Tipo.ADOPCION,
        estado=Postulacion.Estado.DESCARTADA,
        contacto="2901 444444",
    )

    assert postulaciones.motivo_para_no_postularse(ana, ficha) is None
