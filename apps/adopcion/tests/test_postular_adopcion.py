import pytest
from model_bakery import baker

from apps.adopcion import postulaciones
from apps.cuentas import servicios as cuentas
from apps.cuentas.models import Rol, Sancion
from apps.fichas.models import FichaAnimal
from apps.notificaciones.models import Notificacion
from apps.transito.models import Alojamiento, PerfilTransito, Postulacion
from apps.transito.postulaciones import ContactoInvalido, PostulacionNoPermitida

from .conftest import con_perfil, hacer_ficha

Estado = FichaAnimal.Estado

pytestmark = pytest.mark.django_db


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


def test_si_ya_eligieron_adoptante_no_se_aceptan_postulaciones(ana, carla):
    ficha = hacer_ficha()
    baker.make(
        Postulacion,
        ficha=ficha,
        usuario=carla,
        tipo=Postulacion.Tipo.ADOPCION,
        estado=Postulacion.Estado.ELEGIDA,
        contacto="2901 444444",
    )

    assert codigo(con_perfil(ana), ficha) == "ya_hay_adoptante"


def test_queda_una_postulacion_de_adopcion_pendiente(ana):
    ficha = hacer_ficha()

    postulacion = postulaciones.postular_adopcion(con_perfil(ana), ficha, "  2901 444444  ")

    assert postulacion.tipo == Postulacion.Tipo.ADOPCION
    assert postulacion.estado == Postulacion.Estado.PENDIENTE
    assert postulacion.contacto == "2901 444444"
    assert postulacion.ficha == ficha


def test_si_no_puede_postularse_no_se_crea_nada(ana):
    with pytest.raises(PostulacionNoPermitida) as error:
        postulaciones.postular_adopcion(ana, hacer_ficha(), "2901 444444")

    assert error.value.codigo == "perfil_incompleto"
    assert not Postulacion.objects.exists()


@pytest.mark.parametrize("contacto", ["", "   ", "x" * 121])
def test_sin_un_contacto_valido_no_se_crea_nada(ana, contacto):
    with pytest.raises(ContactoInvalido):
        postulaciones.postular_adopcion(con_perfil(ana), hacer_ficha(), contacto)

    assert not Postulacion.objects.exists()


def test_avisa_si_hay_ninos_y_no_sabemos_si_se_lleva_bien_con_ellos(ana):
    con_perfil(ana, hay_ninos=True)

    advertencias = postulaciones.advertencias_de_postulacion(ana, hacer_ficha())

    assert advertencias == [postulaciones.MOTIVO_NINOS]


def test_avisa_si_hay_mascotas_y_no_sabemos_si_se_lleva_bien_con_otros(ana):
    con_perfil(ana, mascotas_propias=2)

    advertencias = postulaciones.advertencias_de_postulacion(ana, hacer_ficha())

    assert advertencias == [postulaciones.MOTIVO_ANIMALES]


def test_sin_avisos_si_la_ficha_dice_que_se_lleva_bien(ana):
    con_perfil(ana, hay_ninos=True, mascotas_propias=2)
    ficha = hacer_ficha(compatible_ninos=True, compatible_animales=True)

    assert postulaciones.advertencias_de_postulacion(ana, ficha) == []


def test_sin_domicilio_no_hay_avisos(ana):
    assert postulaciones.advertencias_de_postulacion(ana, hacer_ficha()) == []


def test_el_cuidador_recibe_un_aviso(ana, beto):
    ficha = hacer_ficha(cuidador=beto, nombre="Firulais")

    postulaciones.postular_adopcion(con_perfil(ana), ficha, "2901 444444")

    aviso = Notificacion.objects.get()
    assert aviso.usuario == beto
    assert aviso.tipo == Notificacion.Tipo.POSTULACION_RECIBIDA
    assert aviso.ficha == ficha
    assert aviso.titulo == "¡Firulais tiene una persona interesada!"
    assert aviso.mensaje == "Alguien quiere darle un hogar."


def test_sin_nombre_el_aviso_habla_de_la_mascota_que_cuida(ana, beto):
    ficha = hacer_ficha(cuidador=beto, nombre="")

    postulaciones.postular_adopcion(con_perfil(ana), ficha, "2901 444444")

    assert (
        Notificacion.objects.get().titulo == "¡La mascota que cuidás tiene una persona interesada!"
    )


def test_sin_cuidador_no_se_avisa_a_nadie(ana):
    postulaciones.postular_adopcion(con_perfil(ana), hacer_ficha(cuidador=None), "2901 444444")

    assert not Notificacion.objects.exists()


def test_el_cuidador_que_se_postula_no_se_avisa_a_si_mismo(ana):
    ficha = hacer_ficha(cuidador=ana)

    postulaciones.postular_adopcion(con_perfil(ana), ficha, "2901 444444")

    assert not Notificacion.objects.exists()
