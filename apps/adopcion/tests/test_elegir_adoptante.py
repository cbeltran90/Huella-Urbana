import pytest
from django.contrib.auth.models import AnonymousUser

from apps.adopcion import eleccion
from apps.cuentas.models import Rol
from apps.fichas.models import FichaAnimal
from apps.notificaciones.models import Notificacion
from apps.transito.models import Postulacion

from .conftest import con_perfil, hacer_ficha

Estado = FichaAnimal.Estado
Tipo, EstadoPostulacion = Postulacion.Tipo, Postulacion.Estado

pytestmark = pytest.mark.django_db


def postular(ficha, usuario, tipo=Tipo.ADOPCION):
    return Postulacion.objects.create(
        ficha=ficha, usuario=usuario, tipo=tipo, contacto="2901 444444"
    )


def moderador(usuario):
    usuario.rol = Rol.MODERADOR
    usuario.save()
    return usuario


# Quién elige


def test_elige_el_cuidador(beto):
    assert eleccion.puede_elegir(beto, hacer_ficha(cuidador=beto))


def test_sin_cuidador_elige_el_responsable(ana):
    assert eleccion.puede_elegir(ana, hacer_ficha(responsable=ana))


def test_con_cuidador_el_responsable_no_elige(ana, beto):
    assert not eleccion.puede_elegir(ana, hacer_ficha(responsable=ana, cuidador=beto))


def test_sin_nadie_a_cargo_elige_un_moderador(beto):
    assert eleccion.puede_elegir(moderador(beto), hacer_ficha())


def test_con_alguien_a_cargo_el_moderador_no_elige(ana, beto):
    assert not eleccion.puede_elegir(moderador(beto), hacer_ficha(cuidador=ana))


def test_otra_persona_o_un_visitante_no_eligen(ana, beto):
    ficha = hacer_ficha(cuidador=beto)

    assert not eleccion.puede_elegir(ana, ficha)
    assert not eleccion.puede_elegir(AnonymousUser(), ficha)


def test_los_postulantes_son_las_postulaciones_de_adopcion_pendientes(ana, beto, carla):
    ficha = hacer_ficha(cuidador=beto)
    pendiente = postular(ficha, ana)
    postular(ficha, carla, Tipo.TRANSITO)

    assert list(eleccion.postulantes_de(ficha)) == [pendiente]


# Elegir


def test_queda_elegida_y_las_demas_de_adopcion_descartadas(ana, beto, carla, django_user_model):
    ficha = hacer_ficha(cuidador=beto)
    elegida = postular(ficha, ana)
    otra = postular(ficha, carla)
    dario = django_user_model.objects.create_user("dario@ejemplo.com", "Dario", "clave-de-prueba-1")
    de_transito = postular(ficha, dario, Tipo.TRANSITO)

    eleccion.elegir_adoptante(elegida, beto)

    elegida.refresh_from_db()
    otra.refresh_from_db()
    de_transito.refresh_from_db()
    assert elegida.estado == EstadoPostulacion.ELEGIDA
    assert otra.estado == EstadoPostulacion.DESCARTADA
    assert de_transito.estado == EstadoPostulacion.PENDIENTE
    assert eleccion.elegida_de(ficha) == elegida


def test_avisa_al_elegido_y_a_los_demas(ana, beto, carla):
    ficha = hacer_ficha(cuidador=beto, nombre="Firulais")
    elegida = postular(ficha, ana)
    postular(ficha, carla)

    eleccion.elegir_adoptante(elegida, beto)

    al_elegido = Notificacion.objects.get(usuario=ana)
    al_otro = Notificacion.objects.get(usuario=carla)
    assert al_elegido.tipo == al_otro.tipo == Notificacion.Tipo.RESULTADO_POSTULACION
    assert al_elegido.titulo == "¡Te eligieron para adoptar a Firulais!"
    assert al_otro.titulo == "Eligieron a otra persona para adoptar a Firulais"
    assert al_elegido.ficha == al_otro.ficha == ficha


def test_sin_telefono_al_elegido_le_dicen_que_lo_van_a_contactar(ana, beto):
    eleccion.elegir_adoptante(postular(hacer_ficha(cuidador=beto), ana), beto)

    assert Notificacion.objects.get().mensaje == eleccion.MENSAJE_AL_ELEGIDO


def test_con_telefono_solo_el_elegido_lo_recibe(ana, beto, carla):
    ficha = hacer_ficha(cuidador=beto)
    elegida = postular(ficha, ana)
    postular(ficha, carla)

    eleccion.elegir_adoptante(elegida, beto, telefono="  2901 444444  ")

    al_elegido = Notificacion.objects.get(usuario=ana)
    al_otro = Notificacion.objects.get(usuario=carla)
    assert al_elegido.mensaje == "Para coordinar la entrega, escribile al 2901 444444."
    assert "2901 444444" not in al_otro.mensaje


def test_sin_nombre_el_aviso_habla_del_animal(ana, beto):
    ficha = hacer_ficha(cuidador=beto, nombre="")

    eleccion.elegir_adoptante(postular(ficha, ana), beto)

    assert Notificacion.objects.get().titulo == "¡Te eligieron para adoptar a la mascota!"


def test_el_cuidador_que_se_elige_a_si_mismo_tambien_recibe_el_aviso(beto):
    ficha = hacer_ficha(cuidador=beto)

    eleccion.elegir_adoptante(postular(ficha, beto), beto)

    assert Notificacion.objects.get().usuario == beto


# Cuándo no se puede


def test_quien_no_lo_tiene_a_cargo_no_puede_elegir(ana, beto, carla):
    elegida = postular(hacer_ficha(cuidador=beto), ana)

    with pytest.raises(eleccion.EleccionNoPermitida):
        eleccion.elegir_adoptante(elegida, carla)

    elegida.refresh_from_db()
    assert elegida.estado == EstadoPostulacion.PENDIENTE


def test_no_se_puede_elegir_dos_veces(ana, beto, carla):
    ficha = hacer_ficha(cuidador=beto)
    eleccion.elegir_adoptante(postular(ficha, ana), beto)
    tardia = postular(ficha, carla)

    with pytest.raises(eleccion.EleccionNoPermitida):
        eleccion.elegir_adoptante(tardia, beto)


def test_una_postulacion_retirada_no_se_puede_elegir(ana, beto):
    retirada = postular(hacer_ficha(cuidador=beto), ana)
    retirada.estado = EstadoPostulacion.DESCARTADA
    retirada.save()

    with pytest.raises(eleccion.EleccionNoPermitida):
        eleccion.elegir_adoptante(retirada, beto)


def test_una_postulacion_de_transito_no_se_elige_como_adoptante(ana, beto):
    de_transito = postular(hacer_ficha(cuidador=beto), ana, Tipo.TRANSITO)

    with pytest.raises(eleccion.EleccionNoPermitida):
        eleccion.elegir_adoptante(de_transito, beto)


def test_si_la_mascota_ya_no_esta_disponible_no_se_elige(ana, beto):
    elegida = postular(hacer_ficha(Estado.REGISTRADO, cuidador=beto), ana)

    with pytest.raises(eleccion.EleccionNoPermitida):
        eleccion.elegir_adoptante(elegida, beto)


# Dudas de compatibilidad, contadas a quien elige


def test_las_dudas_se_cuentan_a_quien_elige(ana):
    postulacion = postular(hacer_ficha(), con_perfil(ana, hay_ninos=True, mascotas_propias=1))

    assert eleccion.dudas_de(postulacion) == [eleccion.DUDA_NINOS, eleccion.DUDA_ANIMALES]


def test_sin_dudas_si_la_ficha_dice_que_se_lleva_bien(ana):
    ficha = hacer_ficha(compatible_ninos=True, compatible_animales=True)
    postulacion = postular(ficha, con_perfil(ana, hay_ninos=True, mascotas_propias=1))

    assert eleccion.dudas_de(postulacion) == []
