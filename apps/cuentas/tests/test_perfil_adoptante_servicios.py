import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import Point

from apps.cuentas import servicios
from apps.cuentas.models import (
    MAX_EXPERIENCIA_PREVIA,
    Domicilio,
    EstadoCuenta,
    PerfilAdoptante,
    Rol,
    Sancion,
    Usuario,
)

CLAVE = "clave-de-prueba-1"
EXACTO = Point(-68.3030, -54.8019, srid=4326)
DESPLAZADO = Point(-68.3040, -54.8025, srid=4326)
HOGAR = {
    "tipo_vivienda": "casa",
    "tiene_patio": True,
    "convivientes": 2,
    "hay_ninos": False,
    "mascotas_propias": 1,
}
EXPERIENCIA = "Tuve dos perros y un gato durante diez años."
FALTAN_TODOS_LOS_DATOS_DEL_HOGAR = [
    "Tipo de vivienda",
    "Patio",
    "Personas con las que convive",
    "Niños en el hogar",
    "Mascotas propias",
]


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def domicilio(usuario, **hogar):
    return Domicilio.objects.create(
        usuario=usuario, ubicacion=EXACTO, ubicacion_desplazada=DESPLAZADO, **hogar
    )


@pytest.fixture
def ana_con_hogar(ana):
    domicilio(ana, **HOGAR)
    return ana


@pytest.mark.django_db
def test_un_perfil_completo_se_guarda(ana_con_hogar):
    perfil = servicios.guardar_perfil_adoptante(ana_con_hogar, f"  {EXPERIENCIA}  ")

    assert perfil.pk == ana_con_hogar.pk
    guardado = PerfilAdoptante.objects.get()
    assert guardado.experiencia_previa == EXPERIENCIA
    assert ana_con_hogar.perfil_adoptante == guardado


@pytest.mark.django_db
def test_sin_domicilio_no_se_guarda_y_se_indica_que_falta(ana):
    with pytest.raises(servicios.PerfilAdoptanteIncompleto) as error:
        servicios.guardar_perfil_adoptante(ana, EXPERIENCIA)

    assert error.value.faltantes == ["Domicilio", *FALTAN_TODOS_LOS_DATOS_DEL_HOGAR]
    assert not PerfilAdoptante.objects.exists()


@pytest.mark.django_db
def test_con_el_domicilio_sin_datos_del_hogar_no_se_guarda(ana):
    domicilio(ana)

    with pytest.raises(servicios.PerfilAdoptanteIncompleto) as error:
        servicios.guardar_perfil_adoptante(ana, EXPERIENCIA)

    assert error.value.faltantes == FALTAN_TODOS_LOS_DATOS_DEL_HOGAR
    assert not PerfilAdoptante.objects.exists()


@pytest.mark.django_db
def test_se_indica_el_dato_del_hogar_que_falta(ana):
    domicilio(ana, **{**HOGAR, "hay_ninos": None})

    with pytest.raises(servicios.PerfilAdoptanteIncompleto) as error:
        servicios.guardar_perfil_adoptante(ana, EXPERIENCIA)

    assert error.value.faltantes == ["Niños en el hogar"]


@pytest.mark.django_db
@pytest.mark.parametrize("experiencia", ["", "   ", None])
def test_sin_experiencia_previa_no_se_guarda(ana_con_hogar, experiencia):
    with pytest.raises(servicios.PerfilAdoptanteIncompleto) as error:
        servicios.guardar_perfil_adoptante(ana_con_hogar, experiencia)

    assert error.value.faltantes == [servicios.ETIQUETA_EXPERIENCIA]
    assert not PerfilAdoptante.objects.exists()


@pytest.mark.django_db
def test_faltan_el_hogar_y_la_experiencia_a_la_vez(ana):
    domicilio(ana, **{**HOGAR, "tipo_vivienda": ""})

    with pytest.raises(servicios.PerfilAdoptanteIncompleto) as error:
        servicios.guardar_perfil_adoptante(ana, "")

    assert error.value.faltantes == ["Tipo de vivienda", servicios.ETIQUETA_EXPERIENCIA]


@pytest.mark.django_db
def test_una_experiencia_demasiado_larga_se_rechaza(ana_con_hogar):
    with pytest.raises(servicios.PerfilAdoptanteInvalido) as error:
        servicios.guardar_perfil_adoptante(ana_con_hogar, "a" * (MAX_EXPERIENCIA_PREVIA + 1))

    assert not isinstance(error.value, servicios.PerfilAdoptanteIncompleto)
    assert str(error.value) == servicios.MENSAJE_EXPERIENCIA_LARGA
    assert not PerfilAdoptante.objects.exists()


@pytest.mark.django_db
def test_el_largo_maximo_se_acepta(ana_con_hogar):
    servicios.guardar_perfil_adoptante(ana_con_hogar, "a" * MAX_EXPERIENCIA_PREVIA)

    assert PerfilAdoptante.objects.count() == 1


@pytest.mark.django_db
def test_guardar_de_nuevo_actualiza_el_mismo_perfil(ana_con_hogar):
    servicios.guardar_perfil_adoptante(ana_con_hogar, "Primera versión")
    servicios.guardar_perfil_adoptante(ana_con_hogar, "Segunda versión")

    assert PerfilAdoptante.objects.count() == 1
    assert PerfilAdoptante.objects.get().experiencia_previa == "Segunda versión"


@pytest.mark.django_db
def test_un_intento_incompleto_no_pisa_el_perfil_anterior(ana_con_hogar):
    servicios.guardar_perfil_adoptante(ana_con_hogar, "Primera versión")

    with pytest.raises(servicios.PerfilAdoptanteIncompleto):
        servicios.guardar_perfil_adoptante(ana_con_hogar, "")

    assert PerfilAdoptante.objects.get().experiencia_previa == "Primera versión"


@pytest.mark.django_db
def test_borrar_la_cuenta_borra_el_perfil(ana_con_hogar):
    servicios.guardar_perfil_adoptante(ana_con_hogar, EXPERIENCIA)

    ana_con_hogar.delete()

    assert not PerfilAdoptante.objects.exists()


@pytest.mark.django_db
def test_con_el_perfil_completo_puede_postularse(ana_con_hogar):
    servicios.guardar_perfil_adoptante(ana_con_hogar, EXPERIENCIA)

    assert servicios.puede_postularse_a_adoptar(ana_con_hogar) is True


@pytest.mark.django_db
def test_sin_perfil_guardado_no_puede_postularse(ana_con_hogar):
    assert servicios.puede_postularse_a_adoptar(ana_con_hogar) is False


@pytest.mark.django_db
def test_sin_domicilio_no_puede_postularse(ana):
    PerfilAdoptante.objects.create(usuario=ana, experiencia_previa=EXPERIENCIA)

    assert servicios.puede_postularse_a_adoptar(ana) is False


@pytest.mark.django_db
def test_con_datos_del_hogar_incompletos_no_puede_postularse(ana):
    domicilio(ana, **{**HOGAR, "mascotas_propias": None})
    PerfilAdoptante.objects.create(usuario=ana, experiencia_previa=EXPERIENCIA)

    assert servicios.puede_postularse_a_adoptar(ana) is False


@pytest.mark.django_db
def test_una_cuenta_suspendida_no_puede_postularse(ana_con_hogar):
    servicios.guardar_perfil_adoptante(ana_con_hogar, EXPERIENCIA)
    moderadora = Usuario.objects.create_user(
        "mod@example.com", "Mod", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, rol=Rol.MODERADOR
    )
    servicios.sancionar(ana_con_hogar, Sancion.Tipo.PERMANENTE, "Motivo", moderadora)

    assert servicios.puede_postularse_a_adoptar(ana_con_hogar) is False


@pytest.mark.django_db
def test_una_cuenta_pendiente_no_puede_postularse(ana_con_hogar):
    servicios.guardar_perfil_adoptante(ana_con_hogar, EXPERIENCIA)
    ana_con_hogar.estado_cuenta = EstadoCuenta.PENDIENTE
    ana_con_hogar.save()

    assert servicios.puede_postularse_a_adoptar(ana_con_hogar) is False


def test_un_visitante_no_puede_postularse():
    assert servicios.puede_postularse_a_adoptar(AnonymousUser()) is False
