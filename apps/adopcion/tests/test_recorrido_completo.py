"""Recorrido completo de tránsito y adopción con los servicios reales de A, B y C (C10)."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.adopcion import eleccion as eleccion_adopcion
from apps.adopcion import entrega
from apps.adopcion import postulaciones as postulaciones_adopcion
from apps.adopcion.models import Adopcion
from apps.cuentas.models import Domicilio, EstadoCuenta
from apps.cuentas.servicios import guardar_domicilio, guardar_perfil_adoptante
from apps.fichas.models import FichaAnimal
from apps.fichas.servicios import crear_ficha_sin_responsable
from apps.notificaciones.models import Notificacion
from apps.publicaciones.models import Publicacion
from apps.transito import eleccion as eleccion_transito
from apps.transito import ingreso, solicitud
from apps.transito import postulaciones as postulaciones_transito
from apps.transito.models import Alojamiento, Postulacion
from apps.transito.servicios import cupo_libre, guardar_perfil_transito

Estado = FichaAnimal.Estado
Tipo = Publicacion.Tipo

VIVIENDA = {
    "tipo_vivienda": "casa",
    "tiene_patio": True,
    "convivientes": 2,
    "hay_ninos": False,
    "mascotas_propias": 0,
}

pytestmark = pytest.mark.django_db


def persona(nombre, lon, lat):
    """Una cuenta activa con domicilio y los datos del hogar completos."""
    usuario = get_user_model().objects.create_user(
        f"{nombre}@ejemplo.com",
        nombre.title(),
        "clave-de-prueba-1",
        estado_cuenta=EstadoCuenta.ACTIVA,
    )
    guardar_domicilio(usuario, Point(lon, lat, srid=4326))
    Domicilio.objects.filter(usuario=usuario).update(**VIVIENDA)
    return usuario


def vigentes(ficha):
    """Los tipos de las publicaciones vigentes de la ficha."""
    return list(
        ficha.publicaciones.filter(estado=Publicacion.Estado.VIGENTE).values_list("tipo", flat=True)
    )


def titulos(usuario):
    return set(Notificacion.objects.filter(usuario=usuario).values_list("titulo", flat=True))


def test_de_la_calle_a_una_familia_pasando_por_un_hogar_de_transito():
    ema = persona("ema", -68.3040, -54.8025)  # la encuentra
    lucia = persona("lucia", -68.2900, -54.8150)  # hogar de tránsito
    guardar_perfil_transito(
        lucia,
        especies=["perro"],
        tamano_maximo="grande",
        duracion_maxima_dias=60,
        cupo_declarado=2,
        disponibilidad=True,
    )
    ana = persona("ana", -68.3100, -54.8060)  # la adopta
    carla = persona("carla", -68.2800, -54.8050)  # también quiere adoptarla
    for adoptante in (ana, carla):
        guardar_perfil_adoptante(adoptante, "Tuve perros toda la vida.")

    # 1. Ema la encuentra y la tiene consigo: ficha pública, sin responsable.
    lola = crear_ficha_sin_responsable(
        {"nombre": "Lola", "especie": "perro", "tamano": "mediano", "color": "negro"},
        cuidador=ema,
    )
    assert (lola.estado, lola.es_privada) == (Estado.SIN_RESPONSABLE, False)

    # 2. Ema pide un hogar de tránsito: la ficha se hace pública y se publica en adopción.
    solicitud.solicitar_transito(lola, ema)
    lola.refresh_from_db()
    assert (lola.estado, lola.es_privada) == (Estado.EN_ADOPCION, False)
    assert vigentes(lola) == [Tipo.ADOPCION]

    # 3 y 4. Lucía se postula como hogar y Ema la elige.
    de_lucia = postulaciones_transito.postular_transito(lucia, lola, "2901 555555")
    eleccion_transito.elegir_hogar(lola, ema, de_lucia)
    assert eleccion_transito.hay_hogar_elegido(lola)

    # 5. Lola llega a la casa de Lucía.
    ingreso.registrar_ingreso(lola, ema, vacunado=True)
    lola.refresh_from_db()
    assert (lola.estado, lola.cuidador) == (Estado.EN_TRANSITO, lucia)
    assert vigentes(lola) == [Tipo.TRANSITO]
    assert cupo_libre(lucia.perfil_transito) == 1

    # 6. Mientras está en tránsito, Ana y Carla se postulan para adoptarla.
    de_ana = postulaciones_adopcion.postular_adopcion(ana, lola, "ana por whatsapp")
    postulaciones_adopcion.postular_adopcion(carla, lola, "carla por mail")

    # 7. Lucía, que ahora la tiene a cargo, elige a Ana.
    eleccion_adopcion.elegir_adoptante(de_ana, lucia)

    # 8. Lucía se la entrega a Ana.
    entrega.concretar_adopcion(lola, lucia)
    lola.refresh_from_db()
    assert (lola.estado, lola.responsable, lola.cuidador) == (Estado.REGISTRADO, ana, None)
    assert vigentes(lola) == []

    adopcion = Adopcion.objects.get(ficha=lola)
    assert (adopcion.adoptante, adopcion.entregado_por) == (ana, lucia)
    alojamiento = Alojamiento.objects.get(ficha=lola)
    assert alojamiento.fecha_fin_real == timezone.localdate()
    assert alojamiento.motivo_fin == Alojamiento.MotivoFin.ADOPCION
    assert cupo_libre(lucia.perfil_transito) == 2

    estados = dict(lola.postulaciones.values_list("usuario__nombre_usuario", "estado"))
    assert estados == {
        "Lucia": Postulacion.Estado.CONCRETADA,
        "Ana": Postulacion.Estado.CONCRETADA,
        "Carla": Postulacion.Estado.DESCARTADA,
    }

    assert "¡Lola ya está en tu hogar!" in titulos(lucia)
    assert "Lola ya está en su hogar de tránsito" in titulos(ema)
    assert "¡Lola ya es parte de tu familia!" in titulos(ana)
    assert "Eligieron a otra persona para adoptar a Lola" in titulos(carla)
