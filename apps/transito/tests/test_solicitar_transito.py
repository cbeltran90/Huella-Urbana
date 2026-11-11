import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.gis.geos import Point

from apps.cuentas.models import Domicilio, EstadoCuenta, Rol, Usuario
from apps.cuentas.servicios import guardar_domicilio
from apps.fichas.models import FichaAnimal
from apps.notificaciones.models import Notificacion
from apps.publicaciones.models import Publicacion
from apps.transito import solicitud
from apps.transito.models import PerfilTransito
from apps.transito.solicitud import ContactoInvalido, SolicitudNoPermitida, UbicacionInvalida

CLAVE = "clave-de-prueba-1"
PUNTO = Point(-68.3040, -54.8025, srid=4326)  # dentro de Ushuaia

pytestmark = pytest.mark.django_db


def crear_usuario(nombre, **campos):
    return Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, **campos
    )


def crear_ficha(**campos):
    datos = {
        "nombre": "Bruno",
        "especie": "perro",
        "tamano": "mediano",
        "estado": FichaAnimal.Estado.SIN_RESPONSABLE,
        "es_privada": True,
        **campos,
    }
    return FichaAnimal.objects.create(**datos)


def crear_hogar(nombre, **perfil):
    usuario = crear_usuario(nombre)
    datos = {
        "especies_aceptadas": "perro",
        "tamano_maximo": "mediano",
        "duracion_maxima_dias": 30,
        "cupo_declarado": 2,
        **perfil,
    }
    PerfilTransito.objects.create(usuario=usuario, **datos)
    return usuario


@pytest.fixture
def cuidador():
    usuario = crear_usuario("carla")
    guardar_domicilio(usuario, PUNTO)
    return usuario


@pytest.fixture
def moderador():
    return crear_usuario("mora", rol=Rol.MODERADOR)


# Quién puede solicitar


def test_el_cuidador_puede_solicitar(cuidador):
    ficha = crear_ficha(cuidador=cuidador)
    assert solicitud.puede_solicitar(cuidador, ficha) is True


def test_un_moderador_puede_solicitar(moderador, cuidador):
    ficha = crear_ficha(cuidador=cuidador)
    assert solicitud.puede_solicitar(moderador, ficha) is True


def test_otro_usuario_no_puede_solicitar(cuidador):
    otra = crear_usuario("otra")
    ficha = crear_ficha(cuidador=cuidador)
    assert solicitud.puede_solicitar(otra, ficha) is False


def test_un_visitante_no_puede_solicitar(cuidador):
    ficha = crear_ficha(cuidador=cuidador)
    assert solicitud.puede_solicitar(AnonymousUser(), ficha) is False


def test_sin_cuidador_solo_puede_un_moderador(moderador):
    otra = crear_usuario("otra")
    ficha = crear_ficha(cuidador=None)
    assert solicitud.puede_solicitar(otra, ficha) is False
    assert solicitud.puede_solicitar(moderador, ficha) is True


@pytest.mark.parametrize(
    "estado",
    [
        FichaAnimal.Estado.REGISTRADO,
        FichaAnimal.Estado.EN_ADOPCION,
        FichaAnimal.Estado.EN_TRANSITO,
    ],
)
def test_solo_se_solicita_con_la_ficha_sin_responsable(cuidador, estado):
    ficha = crear_ficha(estado=estado, cuidador=cuidador)
    assert solicitud.puede_solicitar(cuidador, ficha) is False


# Cuándo hay que marcar el punto


def test_con_domicilio_no_hace_falta_el_punto(cuidador):
    assert solicitud.necesita_punto(crear_ficha(cuidador=cuidador)) is False


def test_sin_domicilio_hace_falta_el_punto():
    assert solicitud.necesita_punto(crear_ficha(cuidador=crear_usuario("sin"))) is True


def test_sin_cuidador_hace_falta_el_punto():
    assert solicitud.necesita_punto(crear_ficha(cuidador=None)) is True


# Solicitar: estado y publicación


def test_la_ficha_pasa_a_en_adopcion_y_queda_publica(cuidador):
    ficha = crear_ficha(cuidador=cuidador)
    solicitud.solicitar_transito(ficha, cuidador)
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.EN_ADOPCION
    assert ficha.es_privada is False
    assert ficha.cuidador == cuidador


def test_se_crea_la_publicacion_de_adopcion(cuidador):
    ficha = crear_ficha(cuidador=cuidador)
    solicitud.solicitar_transito(ficha, cuidador)
    publicacion = Publicacion.objects.get(ficha=ficha)
    assert publicacion.tipo == Publicacion.Tipo.ADOPCION
    assert publicacion.estado == Publicacion.Estado.VIGENTE
    assert publicacion.autor == cuidador


def test_con_domicilio_se_publica_su_punto_aproximado_y_se_ignora_el_enviado(cuidador):
    ficha = crear_ficha(cuidador=cuidador)
    solicitud.solicitar_transito(ficha, cuidador, punto=Point(-68.30, -54.80, srid=4326))
    publicacion = Publicacion.objects.get(ficha=ficha)
    domicilio = Domicilio.objects.get(usuario=cuidador)
    assert publicacion.ubicacion.equals(domicilio.ubicacion_desplazada)


def test_sin_domicilio_se_usa_el_punto_y_queda_como_su_domicilio():
    sin_domicilio = crear_usuario("sin")
    ficha = crear_ficha(cuidador=sin_domicilio)
    solicitud.solicitar_transito(ficha, sin_domicilio, punto=PUNTO)
    domicilio = Domicilio.objects.get(usuario=sin_domicilio)
    publicacion = Publicacion.objects.get(ficha=ficha)
    assert publicacion.ubicacion.equals(domicilio.ubicacion_desplazada)


def test_sin_domicilio_ni_punto_se_pide_la_ubicacion_y_no_cambia_nada():
    sin_domicilio = crear_usuario("sin")
    ficha = crear_ficha(cuidador=sin_domicilio)
    with pytest.raises(UbicacionInvalida):
        solicitud.solicitar_transito(ficha, sin_domicilio)
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.SIN_RESPONSABLE
    assert not Publicacion.objects.filter(ficha=ficha).exists()


def test_un_punto_fuera_de_zona_se_rechaza_y_no_cambia_nada():
    sin_domicilio = crear_usuario("sin")
    ficha = crear_ficha(cuidador=sin_domicilio)
    with pytest.raises(UbicacionInvalida, match="Ushuaia"):
        solicitud.solicitar_transito(ficha, sin_domicilio, punto=Point(0, 0, srid=4326))
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.SIN_RESPONSABLE
    assert not Domicilio.objects.filter(usuario=sin_domicilio).exists()


def test_el_hallazgo_vigente_se_cierra_y_sigue_vinculado(cuidador):
    ficha = crear_ficha(cuidador=cuidador)
    hallazgo = Publicacion.objects.create(
        tipo=Publicacion.Tipo.HALLAZGO,
        autor=cuidador,
        ficha=ficha,
        ubicacion=Point(-68.2999, -54.8011, srid=4326),
    )
    solicitud.solicitar_transito(ficha, cuidador)
    hallazgo.refresh_from_db()
    assert hallazgo.estado == Publicacion.Estado.RESUELTA
    assert hallazgo.ficha == ficha


def test_si_falla_la_publicacion_la_ficha_no_cambia(cuidador, monkeypatch):
    def falla(*args, **kwargs):
        raise ValueError("falla")

    monkeypatch.setattr(solicitud.publicaciones, "publicar_adopcion_de_ficha", falla)
    ficha = crear_ficha(cuidador=cuidador)
    with pytest.raises(ValueError, match="falla"):
        solicitud.solicitar_transito(ficha, cuidador)
    assert FichaAnimal.objects.get(pk=ficha.pk).estado == FichaAnimal.Estado.SIN_RESPONSABLE


# Solicitar: sin cuidador (extensión 1A)


def test_el_moderador_publica_con_el_punto_que_marca(moderador):
    ficha = crear_ficha(cuidador=None)
    solicitud.solicitar_transito(ficha, moderador, punto=PUNTO)
    ficha.refresh_from_db()
    publicacion = Publicacion.objects.get(ficha=ficha)
    assert ficha.estado == FichaAnimal.Estado.EN_ADOPCION
    assert publicacion.autor == moderador
    assert publicacion.ubicacion_desplazada.equals(PUNTO)


def test_el_moderador_sin_punto_no_cambia_nada(moderador):
    ficha = crear_ficha(cuidador=None)
    with pytest.raises(UbicacionInvalida, match="Marcá"):
        solicitud.solicitar_transito(ficha, moderador)
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.SIN_RESPONSABLE
    assert not Publicacion.objects.filter(ficha=ficha).exists()


def test_el_moderador_carga_el_contacto_si_no_hay_cuidador(moderador):
    ficha = crear_ficha(cuidador=None)
    solicitud.solicitar_transito(ficha, moderador, contacto="  Vecina, 2901 555-0101 ", punto=PUNTO)
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.EN_ADOPCION
    assert ficha.cuidador_contacto == "Vecina, 2901 555-0101"


def test_el_contacto_se_ignora_si_hay_cuidador(moderador, cuidador):
    ficha = crear_ficha(cuidador=cuidador)
    solicitud.solicitar_transito(ficha, moderador, contacto="Otra persona")
    ficha.refresh_from_db()
    assert ficha.cuidador_contacto == ""


def test_el_contacto_se_ignora_si_no_es_moderador(cuidador):
    ficha = crear_ficha(cuidador=cuidador)
    solicitud.solicitar_transito(ficha, cuidador, contacto="Otra persona")
    ficha.refresh_from_db()
    assert ficha.cuidador_contacto == ""


def test_un_contacto_demasiado_largo_se_rechaza(moderador):
    ficha = crear_ficha(cuidador=None)
    with pytest.raises(ContactoInvalido):
        solicitud.solicitar_transito(ficha, moderador, contacto="x" * 101, punto=PUNTO)
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.SIN_RESPONSABLE


# Solicitar: permisos y concurrencia


def test_quien_no_puede_no_cambia_la_ficha(cuidador):
    otra = crear_usuario("otra")
    ficha = crear_ficha(cuidador=cuidador)
    with pytest.raises(SolicitudNoPermitida):
        solicitud.solicitar_transito(ficha, otra)
    ficha.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.SIN_RESPONSABLE
    assert ficha.es_privada is True
    assert not Publicacion.objects.filter(ficha=ficha).exists()


def test_si_otro_cambio_el_estado_no_se_pisa(cuidador):
    ficha = crear_ficha(cuidador=cuidador)
    FichaAnimal.objects.filter(pk=ficha.pk).update(estado=FichaAnimal.Estado.REGISTRADO)
    with pytest.raises(SolicitudNoPermitida):
        solicitud.solicitar_transito(ficha, cuidador)
    assert FichaAnimal.objects.get(pk=ficha.pk).estado == FichaAnimal.Estado.REGISTRADO


# Avisos a los hogares


def test_se_avisa_solo_a_los_hogares_compatibles(cuidador):
    compatible = crear_hogar("lucia")
    solo_gatos = crear_hogar("romina", especies_aceptadas="gato")
    ficha = crear_ficha(cuidador=cuidador)

    solicitud.solicitar_transito(ficha, cuidador)

    avisados = set(
        Notificacion.objects.filter(
            tipo=Notificacion.Tipo.COINCIDENCIA_TRANSITO, ficha=ficha
        ).values_list("usuario", flat=True)
    )
    assert avisados == {compatible.pk}
    assert solo_gatos.pk not in avisados
