from datetime import timedelta

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.cuentas.models import Domicilio, EstadoCuenta, Usuario
from apps.fichas.models import FichaAnimal
from apps.notificaciones.models import Notificacion
from apps.publicaciones.models import Publicacion
from apps.transito import eleccion, ingreso
from apps.transito.models import Alojamiento, PerfilTransito, Postulacion
from apps.transito.servicios import cupo_libre

CLAVE = "clave-de-prueba-1"
PUNTO = Point(-68.3030, -54.8019, srid=4326)
Estado = FichaAnimal.Estado

pytestmark = pytest.mark.django_db


def crear_usuario(nombre):
    return Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def crear_hogar(nombre, **perfil):
    """Un hogar de tránsito con domicilio (la publicación de tránsito usa su punto)."""
    usuario = crear_usuario(nombre)
    Domicilio.objects.create(usuario=usuario, ubicacion=PUNTO, ubicacion_desplazada=PUNTO)
    datos = {
        "especies_aceptadas": "perro",
        "tamano_maximo": "grande",
        "duracion_maxima_dias": 30,
        "cupo_declarado": 1,
        **perfil,
    }
    PerfilTransito.objects.create(usuario=usuario, **datos)
    return usuario


def elegir_hogar(ficha, hogar):
    return Postulacion.objects.create(
        ficha=ficha,
        usuario=hogar,
        tipo=Postulacion.Tipo.TRANSITO,
        estado=Postulacion.Estado.ELEGIDA,
        contacto="2901-555555",
    )


def ingresar(ficha, actor, **sanidad):
    return ingreso.registrar_ingreso(ficha, actor, **sanidad)


@pytest.fixture
def beto():
    """Cuida a la mascota y la entrega."""
    return crear_usuario("beto")


@pytest.fixture
def hogar():
    return crear_hogar("hogar")


@pytest.fixture
def ficha(beto):
    return FichaAnimal.objects.create(
        nombre="Firulais",
        especie="perro",
        tamano="mediano",
        estado=Estado.EN_ADOPCION,
        es_privada=False,
        cuidador=beto,
    )


# Lo que queda al registrar el ingreso


def test_la_mascota_pasa_a_transito_a_cargo_del_hogar(ficha, beto, hogar):
    elegir_hogar(ficha, hogar)

    ingresar(ficha, beto)

    ficha.refresh_from_db()
    assert ficha.estado == Estado.EN_TRANSITO
    assert ficha.cuidador == hogar


def test_queda_el_alojamiento_con_su_fecha_de_fin_y_la_sanidad(ficha, beto, hogar):
    elegir_hogar(ficha, hogar)

    ingresar(ficha, beto, vacunado=True, desparasitado=True)

    alojamiento = Alojamiento.objects.get()
    hoy = timezone.localdate()
    assert alojamiento.hogar == hogar.perfil_transito
    assert alojamiento.fecha_ingreso == hoy
    assert alojamiento.fecha_fin_prevista == hoy + timedelta(days=30)
    assert alojamiento.vacunado_al_ingreso and alojamiento.desparasitado_al_ingreso
    assert not alojamiento.castrado_al_ingreso


def test_el_hogar_ocupa_una_plaza(ficha, beto, hogar):
    elegir_hogar(ficha, hogar)

    ingresar(ficha, beto)

    assert cupo_libre(hogar.perfil_transito) == 0


def test_la_postulacion_del_hogar_queda_concretada(ficha, beto, hogar):
    elegida = elegir_hogar(ficha, hogar)

    ingresar(ficha, beto)

    elegida.refresh_from_db()
    assert elegida.estado == Postulacion.Estado.CONCRETADA


def test_la_publicacion_pasa_de_adopcion_a_transito(ficha, beto, hogar):
    adopcion = Publicacion.objects.create(
        tipo=Publicacion.Tipo.ADOPCION, autor=beto, ficha=ficha, ubicacion=PUNTO
    )
    elegir_hogar(ficha, hogar)

    ingresar(ficha, beto)

    adopcion.refresh_from_db()
    assert adopcion.estado == Publicacion.Estado.RESUELTA
    assert ficha.publicaciones.filter(
        tipo=Publicacion.Tipo.TRANSITO, estado=Publicacion.Estado.VIGENTE
    ).exists()


def test_avisa_al_hogar_y_a_quien_la_entrega(ficha, beto, hogar):
    elegir_hogar(ficha, hogar)

    ingresar(ficha, beto)

    fin = timezone.localdate() + timedelta(days=30)
    al_hogar = Notificacion.objects.get(usuario=hogar)
    al_que_entrega = Notificacion.objects.get(usuario=beto)
    assert al_hogar.titulo == "¡Firulais ya está en tu hogar!"
    assert f"hasta el {fin:%d/%m}" in al_hogar.mensaje
    assert al_que_entrega.titulo == "Firulais ya está en su hogar de tránsito"


# Quién puede y cuándo


def test_el_hogar_elegido_tambien_puede_marcar_el_ingreso(ficha, hogar):
    elegir_hogar(ficha, hogar)

    ingresar(ficha, hogar)

    ficha.refresh_from_db()
    assert ficha.estado == Estado.EN_TRANSITO


def test_otra_persona_no_puede(ficha, hogar):
    elegir_hogar(ficha, hogar)

    with pytest.raises(ingreso.IngresoNoPermitido):
        ingresar(ficha, crear_usuario("dario"))

    assert not Alojamiento.objects.exists()


def test_sin_hogar_elegido_no_se_puede(ficha, beto):
    with pytest.raises(ingreso.IngresoNoPermitido):
        ingresar(ficha, beto)


def test_si_el_hogar_ya_no_tiene_lugar_no_ingresa(ficha, beto, hogar):
    otra = FichaAnimal.objects.create(especie="perro", estado=Estado.EN_TRANSITO, cuidador=hogar)
    Alojamiento.objects.create(
        ficha=otra,
        hogar=hogar.perfil_transito,
        fecha_fin_prevista=timezone.localdate() + timedelta(days=10),
    )
    elegir_hogar(ficha, hogar)

    with pytest.raises(ingreso.IngresoNoPermitido, match="lugar libre"):
        ingresar(ficha, beto)

    ficha.refresh_from_db()
    assert ficha.estado == Estado.EN_ADOPCION


def test_si_el_hogar_esta_en_pausa_no_ingresa(ficha, beto):
    en_pausa = crear_hogar(
        "pausado",
        disponibilidad=False,
        pausa_hasta=timezone.localdate() + timedelta(days=5),
    )
    elegir_hogar(ficha, en_pausa)

    with pytest.raises(ingreso.IngresoNoPermitido, match="ya no está disponible"):
        ingresar(ficha, beto)


# Cancelar la entrega (1A)


def test_al_cancelar_la_mascota_sigue_en_adopcion(ficha, beto, hogar):
    elegida = elegir_hogar(ficha, hogar)

    ingreso.cancelar_entrega(ficha, beto)

    elegida.refresh_from_db()
    ficha.refresh_from_db()
    assert elegida.estado == Postulacion.Estado.DESCARTADA
    assert ficha.estado == Estado.EN_ADOPCION
    assert ficha.cuidador == beto
    assert not Alojamiento.objects.exists()


def test_despues_de_cancelar_se_puede_elegir_otro_hogar(ficha, beto, hogar):
    elegir_hogar(ficha, hogar)

    ingreso.cancelar_entrega(ficha, beto)

    assert not eleccion.hay_hogar_elegido(ficha)


def test_si_cancela_quien_entrega_se_avisa_al_hogar(ficha, beto, hogar):
    elegir_hogar(ficha, hogar)

    ingreso.cancelar_entrega(ficha, beto)

    aviso = Notificacion.objects.get()
    assert aviso.usuario == hogar
    assert aviso.titulo == "La entrega de Firulais no se concretó"


def test_si_cancela_el_hogar_se_avisa_a_quien_entrega(ficha, beto, hogar):
    elegir_hogar(ficha, hogar)

    ingreso.cancelar_entrega(ficha, hogar)

    aviso = Notificacion.objects.get()
    assert aviso.usuario == beto
    assert aviso.titulo == "El hogar de tránsito canceló la entrega de Firulais"


def test_otra_persona_no_puede_cancelar(ficha, hogar):
    elegida = elegir_hogar(ficha, hogar)

    with pytest.raises(ingreso.IngresoNoPermitido):
        ingreso.cancelar_entrega(ficha, crear_usuario("dario"))

    elegida.refresh_from_db()
    assert elegida.estado == Postulacion.Estado.ELEGIDA
