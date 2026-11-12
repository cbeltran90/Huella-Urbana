import pytest
from django.utils import timezone
from model_bakery import baker

from apps.adopcion import entrega
from apps.adopcion.models import Adopcion
from apps.cuentas.models import Rol
from apps.fichas.models import FichaAnimal
from apps.notificaciones.models import Notificacion
from apps.publicaciones.models import Publicacion
from apps.transito.models import Alojamiento, PerfilTransito, Postulacion

from .conftest import PUNTO, hacer_ficha

Estado = FichaAnimal.Estado
Tipo, EstadoPostulacion = Postulacion.Tipo, Postulacion.Estado

pytestmark = pytest.mark.django_db


def postular(ficha, usuario, tipo=Tipo.ADOPCION, estado=EstadoPostulacion.PENDIENTE):
    return Postulacion.objects.create(
        ficha=ficha, usuario=usuario, tipo=tipo, estado=estado, contacto="2901 444444"
    )


def elegir(ficha, usuario):
    return postular(ficha, usuario, estado=EstadoPostulacion.ELEGIDA)


# Lo que queda al concretar


def test_la_mascota_queda_registrada_con_quien_adopta(ana, beto):
    ficha = hacer_ficha(cuidador=beto)
    elegir(ficha, ana)

    entrega.concretar_adopcion(ficha, beto)

    ficha.refresh_from_db()
    assert ficha.estado == Estado.REGISTRADO
    assert ficha.responsable == ana
    assert ficha.cuidador is None


def test_queda_registrada_la_adopcion_y_la_postulacion_concretada(ana, beto):
    ficha = hacer_ficha(cuidador=beto)
    elegida = elegir(ficha, ana)

    entrega.concretar_adopcion(ficha, beto)

    adopcion = Adopcion.objects.get()
    assert (adopcion.ficha, adopcion.adoptante, adopcion.entregado_por) == (ficha, ana, beto)
    elegida.refresh_from_db()
    assert elegida.estado == EstadoPostulacion.CONCRETADA


def test_sin_cuidador_entrega_el_responsable(ana, carla):
    ficha = hacer_ficha(responsable=carla)
    elegir(ficha, ana)

    entrega.concretar_adopcion(ficha, carla)

    assert Adopcion.objects.get().entregado_por == carla


def test_si_el_cuidador_se_la_queda_nadie_la_entrega(beto):
    ficha = hacer_ficha(cuidador=beto)
    elegir(ficha, beto)

    entrega.concretar_adopcion(ficha, beto)

    assert Adopcion.objects.get().entregado_por is None


def test_la_publicacion_de_adopcion_queda_resuelta(ana, beto):
    ficha = hacer_ficha(cuidador=beto)
    publicacion = Publicacion.objects.create(
        tipo=Publicacion.Tipo.ADOPCION, autor=beto, ficha=ficha, ubicacion=PUNTO
    )
    elegir(ficha, ana)

    entrega.concretar_adopcion(ficha, beto)

    publicacion.refresh_from_db()
    assert publicacion.estado == Publicacion.Estado.RESUELTA


def test_desde_un_hogar_de_transito_se_libera_la_plaza(ana, carla):
    ficha = hacer_ficha(Estado.EN_TRANSITO, cuidador=carla)
    hogar = baker.make(PerfilTransito, usuario=carla)
    alojamiento = baker.make(Alojamiento, ficha=ficha, hogar=hogar, fecha_fin_real=None)
    elegir(ficha, ana)

    entrega.concretar_adopcion(ficha, carla)

    alojamiento.refresh_from_db()
    assert alojamiento.fecha_fin_real == timezone.localdate()
    assert alojamiento.motivo_fin == Alojamiento.MotivoFin.ADOPCION
    ficha.refresh_from_db()
    assert ficha.estado == Estado.REGISTRADO


def test_se_descartan_las_postulaciones_que_quedaban(ana, beto, carla, django_user_model):
    ficha = hacer_ficha(cuidador=beto)
    elegir(ficha, ana)
    pendiente = postular(ficha, carla, Tipo.TRANSITO)
    dario = django_user_model.objects.create_user("dario@ejemplo.com", "Dario", "clave-de-prueba-1")
    hogar_elegido = postular(ficha, dario, Tipo.TRANSITO, EstadoPostulacion.ELEGIDA)

    entrega.concretar_adopcion(ficha, beto)

    pendiente.refresh_from_db()
    hogar_elegido.refresh_from_db()
    assert pendiente.estado == hogar_elegido.estado == EstadoPostulacion.DESCARTADA


def test_avisa_a_quien_adopta_y_a_quienes_quedaban(ana, beto, carla):
    ficha = hacer_ficha(cuidador=beto, nombre="Firulais")
    elegir(ficha, ana)
    postular(ficha, carla, Tipo.TRANSITO)

    entrega.concretar_adopcion(ficha, beto)

    assert Notificacion.objects.get(usuario=ana).titulo == "¡Firulais ya es parte de tu familia!"
    assert Notificacion.objects.get(usuario=carla).titulo == "Firulais ya encontró un hogar"


# Quién puede y cuándo


def test_un_moderador_siempre_puede_concretar(ana, beto, carla):
    carla.rol = Rol.MODERADOR
    carla.save()
    ficha = hacer_ficha(cuidador=beto)
    elegir(ficha, ana)

    entrega.concretar_adopcion(ficha, carla)

    ficha.refresh_from_db()
    assert ficha.responsable == ana


def test_otra_persona_no_puede_concretar(ana, beto, carla):
    ficha = hacer_ficha(cuidador=beto)
    elegida = elegir(ficha, ana)

    with pytest.raises(entrega.EntregaNoPermitida):
        entrega.concretar_adopcion(ficha, carla)

    elegida.refresh_from_db()
    assert elegida.estado == EstadoPostulacion.ELEGIDA
    assert not Adopcion.objects.exists()


def test_sin_adoptante_elegido_no_se_puede(ana, beto):
    ficha = hacer_ficha(cuidador=beto)
    postular(ficha, ana)

    with pytest.raises(entrega.EntregaNoPermitida):
        entrega.concretar_adopcion(ficha, beto)

    ficha.refresh_from_db()
    assert ficha.estado == Estado.EN_ADOPCION
