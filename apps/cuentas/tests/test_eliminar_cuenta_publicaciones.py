"""Al eliminar la cuenta, qué pasa con las publicaciones que salían de su domicilio."""

import pytest
from django.contrib.gis.geos import Point

from apps.cuentas.eliminacion import eliminar_cuenta
from apps.cuentas.models import Domicilio, EstadoCuenta, Usuario
from apps.cuentas.servicios import guardar_domicilio
from apps.publicaciones.models import Publicacion

CLAVE = "clave-de-prueba-1"
EXACTO = Point(-68.3100, -54.8100, srid=4326)

pytestmark = pytest.mark.django_db


def cuenta(correo, nombre):
    return Usuario.objects.create_user(correo, nombre, CLAVE, estado_cuenta=EstadoCuenta.ACTIVA)


def con_domicilio(usuario):
    guardar_domicilio(usuario, EXACTO)
    return Domicilio.objects.get(usuario=usuario)


def publicar(autor, domicilio):
    """Una publicación cuyo punto sale de ese domicilio (siempre el punto desplazado)."""
    return Publicacion.objects.create(
        tipo=Publicacion.Tipo.HALLAZGO,
        autor=autor,
        ubicacion=domicilio.ubicacion_desplazada,
        domicilio=domicilio,
        descripcion="Texto",
    )


def test_sus_publicaciones_conservan_el_punto_y_pierden_la_referencia_al_domicilio():
    ana = cuenta("ana@example.com", "Ana")
    domicilio = con_domicilio(ana)
    publicacion = publicar(ana, domicilio)
    punto = publicacion.ubicacion

    eliminar_cuenta(ana)

    publicacion.refresh_from_db()
    assert publicacion.domicilio is None
    assert publicacion.ubicacion.equals_exact(punto, 1e-9)
    assert not Domicilio.objects.filter(pk=domicilio.pk).exists()


def test_el_punto_que_queda_es_el_desplazado_no_el_exacto():
    ana = cuenta("ana@example.com", "Ana")
    publicacion = publicar(ana, con_domicilio(ana))

    eliminar_cuenta(ana)

    publicacion.refresh_from_db()
    assert not publicacion.ubicacion.equals_exact(EXACTO, 1e-9)


def test_una_publicacion_de_otra_persona_con_su_domicilio_solo_pierde_la_referencia():
    ana = cuenta("ana@example.com", "Ana")
    beto = cuenta("beto@example.com", "Beto")
    publicacion = publicar(beto, con_domicilio(ana))
    punto = publicacion.ubicacion

    eliminar_cuenta(ana)

    publicacion.refresh_from_db()
    assert publicacion.autor == beto
    assert publicacion.estado == Publicacion.Estado.VIGENTE
    assert publicacion.descripcion == "Texto"
    assert publicacion.domicilio is None
    assert publicacion.ubicacion.equals_exact(punto, 1e-9)
