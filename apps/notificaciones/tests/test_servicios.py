import pytest
from django.contrib.gis.geos import Point
from model_bakery import baker

from apps.fichas.models import FichaAnimal
from apps.notificaciones.models import Notificacion
from apps.notificaciones.servicios import notificar
from apps.publicaciones.models import Publicacion

Tipo = Notificacion.Tipo

pytestmark = pytest.mark.django_db


def test_crea_la_notificacion_con_los_datos_y_los_valores_por_defecto(ana):
    n = notificar(ana, Tipo.EVENTO, "Jornada de vacunación", "Sábado en el gimnasio")
    n.refresh_from_db()

    assert n.usuario == ana
    assert n.tipo == Tipo.EVENTO
    assert n.titulo == "Jornada de vacunación"
    assert n.mensaje == "Sábado en el gimnasio"
    assert n.leida is False
    assert n.push_enviado_at is None
    assert n.reintentos == 0
    assert n.ficha is None
    assert n.publicacion is None


def test_vincula_la_ficha_y_la_publicacion(ana):
    ficha = baker.make(FichaAnimal, especie="perro")
    publicacion = baker.make(
        Publicacion,
        tipo=Publicacion.Tipo.EXTRAVIO,
        ficha=ficha,
        ubicacion=Point(-68.3040, -54.8025, srid=4326),
    )

    n = notificar(ana, Tipo.FAVORITO, "novedad", ficha=ficha, publicacion=publicacion)

    assert n.ficha == ficha
    assert n.publicacion == publicacion
    assert ficha.notificaciones.count() == 1


def test_un_tipo_invalido_lanza_error_y_no_crea_nada(ana):
    with pytest.raises(ValueError):
        notificar(ana, "coincidencia", "No debería existir")

    assert not Notificacion.objects.exists()
