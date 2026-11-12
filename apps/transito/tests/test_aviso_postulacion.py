import pytest

from apps.cuentas.models import EstadoCuenta, Usuario
from apps.fichas.models import FichaAnimal
from apps.notificaciones.models import Notificacion
from apps.transito import postulaciones
from apps.transito.models import PerfilTransito, Postulacion

CLAVE = "clave-de-prueba-1"

pytestmark = pytest.mark.django_db


def crear_usuario(nombre):
    return Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def crear_hogar(nombre="lucia"):
    usuario = crear_usuario(nombre)
    PerfilTransito.objects.create(
        usuario=usuario,
        especies_aceptadas="perro",
        tamano_maximo="mediano",
        duracion_maxima_dias=30,
        cupo_declarado=2,
    )
    return usuario


def crear_ficha(**campos):
    datos = {
        "nombre": "Bruno",
        "especie": "perro",
        "tamano": "mediano",
        "estado": FichaAnimal.Estado.EN_ADOPCION,
        "es_privada": False,
        **campos,
    }
    return FichaAnimal.objects.create(**datos)


def avisos():
    return Notificacion.objects.filter(tipo=Notificacion.Tipo.POSTULACION_RECIBIDA)


def test_se_avisa_a_quien_tiene_el_animal_a_su_cargo():
    cuidador = crear_usuario("carla")
    ficha = crear_ficha(cuidador=cuidador)

    postulaciones.postular_transito(crear_hogar(), ficha, "2901-555555")

    aviso = avisos().get()
    assert aviso.usuario == cuidador
    assert aviso.ficha == ficha
    assert aviso.titulo == "Nueva postulación de tránsito"
    assert "postulación nueva" in aviso.mensaje
    assert "Bruno" in aviso.mensaje


def test_el_aviso_no_dice_quien_se_postulo():
    ficha = crear_ficha(cuidador=crear_usuario("carla"))
    hogar = crear_hogar()

    postulaciones.postular_transito(hogar, ficha, "2901-555555")

    aviso = avisos().get()
    assert hogar.nombre_usuario not in aviso.mensaje
    assert "2901-555555" not in aviso.mensaje


def test_si_solo_hay_responsable_se_le_avisa_a_el():
    responsable = crear_usuario("rosa")
    ficha = crear_ficha(responsable=responsable)

    postulaciones.postular_transito(crear_hogar(), ficha, "2901-555555")

    assert [aviso.usuario for aviso in avisos()] == [responsable]


def test_si_hay_cuidador_y_responsable_distintos_se_avisa_a_los_dos():
    cuidador = crear_usuario("carla")
    responsable = crear_usuario("rosa")
    ficha = crear_ficha(cuidador=cuidador, responsable=responsable)

    postulaciones.postular_transito(crear_hogar(), ficha, "2901-555555")

    assert {aviso.usuario for aviso in avisos()} == {cuidador, responsable}
    assert avisos().count() == 2


def test_si_son_la_misma_persona_se_avisa_una_sola_vez():
    persona = crear_usuario("carla")
    ficha = crear_ficha(cuidador=persona, responsable=persona)

    postulaciones.postular_transito(crear_hogar(), ficha, "2901-555555")

    assert avisos().count() == 1


def test_sin_cuidador_ni_responsable_no_se_avisa_a_nadie_y_la_postulacion_queda():
    ficha = crear_ficha()

    postulaciones.postular_transito(crear_hogar(), ficha, "2901-555555")

    assert avisos().count() == 0
    assert Postulacion.objects.filter(ficha=ficha).count() == 1


def test_si_el_aviso_falla_la_postulacion_queda(monkeypatch):
    def falla(*args, **kwargs):
        raise RuntimeError("falla")

    monkeypatch.setattr(postulaciones, "notificar", falla)
    ficha = crear_ficha(cuidador=crear_usuario("carla"))

    postulaciones.postular_transito(crear_hogar(), ficha, "2901-555555")

    assert Postulacion.objects.filter(ficha=ficha).count() == 1


def test_si_no_puede_postularse_no_se_avisa():
    ficha = crear_ficha(cuidador=crear_usuario("carla"))
    sin_perfil = crear_usuario("sinperfil")

    with pytest.raises(postulaciones.PostulacionNoPermitida):
        postulaciones.postular_transito(sin_perfil, ficha, "2901-555555")

    assert avisos().count() == 0
    assert not Postulacion.objects.exists()


def test_no_se_avisa_al_propio_postulante():
    cuidador = crear_usuario("carla")
    ficha = crear_ficha(cuidador=cuidador)
    postulacion = Postulacion.objects.create(
        ficha=ficha, usuario=cuidador, tipo=Postulacion.Tipo.ADOPCION, contacto="2901-555555"
    )

    postulaciones.avisar_de_postulacion(postulacion)

    assert avisos().count() == 0


def test_si_el_postulante_es_el_responsable_solo_se_avisa_al_cuidador():
    cuidador = crear_usuario("carla")
    responsable = crear_usuario("rosa")
    ficha = crear_ficha(cuidador=cuidador, responsable=responsable)
    postulacion = Postulacion.objects.create(
        ficha=ficha, usuario=responsable, tipo=Postulacion.Tipo.ADOPCION, contacto="2901-555555"
    )

    postulaciones.avisar_de_postulacion(postulacion)

    assert [aviso.usuario for aviso in avisos()] == [cuidador]


def test_el_aviso_de_adopcion_dice_lo_mismo_que_el_de_adopcion_de_siempre():
    cuidador = crear_usuario("carla")
    ficha = crear_ficha(cuidador=cuidador, nombre="Firulais")
    postulacion = Postulacion.objects.create(
        ficha=ficha,
        usuario=crear_usuario("ana"),
        tipo=Postulacion.Tipo.ADOPCION,
        contacto="2901-555555",
    )

    postulaciones.avisar_de_postulacion(postulacion)

    aviso = avisos().get()
    assert aviso.usuario == cuidador
    assert aviso.titulo == "¡Firulais tiene una persona interesada!"
    assert aviso.mensaje == "Alguien quiere darle un hogar."


def test_sin_nombre_el_aviso_de_adopcion_habla_de_la_mascota_que_cuida():
    ficha = crear_ficha(cuidador=crear_usuario("carla"), nombre="")
    postulacion = Postulacion.objects.create(
        ficha=ficha,
        usuario=crear_usuario("ana"),
        tipo=Postulacion.Tipo.ADOPCION,
        contacto="2901-555555",
    )

    postulaciones.avisar_de_postulacion(postulacion)

    assert avisos().get().titulo == "¡La mascota que cuidás tiene una persona interesada!"


def test_sin_nombre_el_aviso_de_transito_habla_de_la_mascota():
    ficha = crear_ficha(cuidador=crear_usuario("carla"), nombre="")

    postulaciones.postular_transito(crear_hogar(), ficha, "2901-555555")

    assert avisos().get().mensaje == "Hay una postulación nueva de tránsito para la mascota."
