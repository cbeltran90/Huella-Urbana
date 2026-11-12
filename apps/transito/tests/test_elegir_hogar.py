from datetime import timedelta

import pytest
from django.utils import timezone

from apps.cuentas.models import EstadoCuenta, Rol, Sancion, Usuario
from apps.fichas.models import FichaAnimal
from apps.notificaciones.models import Notificacion
from apps.transito import eleccion
from apps.transito.models import Alojamiento, PerfilTransito, Postulacion

CLAVE = "clave-de-prueba-1"

pytestmark = pytest.mark.django_db


def crear_usuario(nombre, **campos):
    return Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, **campos
    )


def crear_hogar(nombre, **perfil):
    usuario = crear_usuario(nombre)
    datos = {
        "especies_aceptadas": "perro",
        "tamano_maximo": "grande",
        "duracion_maxima_dias": 30,
        "cupo_declarado": 2,
        **perfil,
    }
    PerfilTransito.objects.create(usuario=usuario, **datos)
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


def postular(usuario, ficha, tipo=Postulacion.Tipo.TRANSITO, **campos):
    return Postulacion.objects.create(
        ficha=ficha, usuario=usuario, tipo=tipo, contacto="2901-555555", **campos
    )


def avisos():
    return Notificacion.objects.filter(tipo=Notificacion.Tipo.RESULTADO_POSTULACION)


def suspender(usuario):
    Sancion.objects.create(
        usuario=usuario,
        email_hash=usuario.email_hash,
        tipo=Sancion.Tipo.TEMPORAL,
        motivo="Motivo de prueba",
        fin=timezone.now() + timedelta(days=3),
    )


@pytest.fixture
def carla():
    return crear_usuario("carla")


@pytest.fixture
def ficha(carla):
    return crear_ficha(cuidador=carla)


# Quién puede elegir


def test_pueden_elegir_el_cuidador_el_responsable_y_el_moderador(carla):
    responsable = crear_usuario("rosa")
    ficha = crear_ficha(cuidador=carla, responsable=responsable)
    moderador = crear_usuario("mora", rol=Rol.MODERADOR)

    assert eleccion.puede_elegir(carla, ficha)
    assert eleccion.puede_elegir(responsable, ficha)
    assert eleccion.puede_elegir(moderador, ficha)


def test_puede_elegir_el_hogar_que_aloja_al_animal_en_relevo():
    hogar = crear_hogar("lucia")
    ficha = crear_ficha()
    Alojamiento.objects.create(
        ficha=ficha, hogar=hogar.perfil_transito, fecha_fin_prevista=timezone.localdate()
    )

    assert eleccion.puede_elegir(hogar, ficha)


def test_un_ajeno_o_un_hogar_postulante_no_puede_elegir(ficha):
    ajeno = crear_usuario("ana")
    postulante = crear_hogar("lucia")
    postular(postulante, ficha)

    assert not eleccion.puede_elegir(ajeno, ficha)
    assert not eleccion.puede_elegir(postulante, ficha)


def test_con_otro_estado_nadie_puede_elegir(carla):
    ficha = crear_ficha(cuidador=carla, estado=FichaAnimal.Estado.EN_TRANSITO)

    assert not eleccion.puede_elegir(carla, ficha)


# Postulantes habilitados


def test_lista_los_postulantes_de_transito_pendientes_del_mas_antiguo_al_mas_nuevo(ficha):
    ahora = timezone.now()
    nuevo = crear_hogar("nuevo")
    antiguo = crear_hogar("antiguo")
    postular(nuevo, ficha, fecha=ahora)
    postular(antiguo, ficha, fecha=ahora - timedelta(hours=2))

    postulantes = eleccion.postulantes_habilitados(ficha)

    assert [p.postulacion.usuario for p in postulantes] == [antiguo, nuevo]
    assert postulantes[0].contacto == "2901-555555"
    assert postulantes[0].cupo_libre == 2


def test_no_lista_a_quienes_no_estan_habilitados(ficha):
    habilitado = crear_hogar("lucia")
    en_pausa = crear_hogar(
        "pausa", disponibilidad=False, pausa_hasta=timezone.localdate() + timedelta(days=10)
    )
    suspendido = crear_hogar("suspendido")
    suspender(suspendido)
    desactivado = crear_hogar("desactivado", activo=False)
    for hogar in (habilitado, en_pausa, suspendido, desactivado):
        postular(hogar, ficha)

    assert [p.postulacion.usuario for p in eleccion.postulantes_habilitados(ficha)] == [habilitado]


def test_no_lista_adopciones_ni_postulaciones_descartadas_ni_de_otra_ficha(ficha):
    adoptante = crear_hogar("ana")
    retirado = crear_hogar("retirado")
    de_otra = crear_hogar("otra")
    postular(adoptante, ficha, tipo=Postulacion.Tipo.ADOPCION)
    postular(retirado, ficha, estado=Postulacion.Estado.DESCARTADA)
    postular(de_otra, crear_ficha())

    assert eleccion.postulantes_habilitados(ficha) == []


def test_un_hogar_con_el_cupo_completo_sigue_apareciendo(ficha):
    hogar = crear_hogar("lucia", cupo_declarado=1)
    Alojamiento.objects.create(
        ficha=crear_ficha(), hogar=hogar.perfil_transito, fecha_fin_prevista=timezone.localdate()
    )
    postular(hogar, ficha)

    postulante = eleccion.postulantes_habilitados(ficha)[0]

    assert postulante.cupo_libre == 0


def test_muestra_por_que_no_encaja_y_deja_vacia_la_lista_si_encaja(carla):
    ficha = crear_ficha(cuidador=carla, especie="gato", tamano="grande")
    encaja = crear_hogar("encaja", especies_aceptadas="gato,perro")
    no_encaja = crear_hogar("noencaja", tamano_maximo="pequeno")
    postular(encaja, ficha)
    postular(no_encaja, ficha)

    por_hogar = {p.postulacion.usuario: p for p in eleccion.postulantes_habilitados(ficha)}

    assert por_hogar[encaja].advertencias == []
    assert len(por_hogar[no_encaja].advertencias) == 2


# Elegir


def test_elige_uno_descarta_a_los_demas_y_avisa_a_todos(carla, ficha):
    elegido = crear_hogar("lucia")
    otro = crear_hogar("otro")
    tercero = crear_hogar("tercero")
    p_elegida = postular(elegido, ficha)
    p_otro = postular(otro, ficha)
    p_tercero = postular(tercero, ficha)

    resultado = eleccion.elegir_hogar(ficha, carla, p_elegida)

    assert resultado.estado == Postulacion.Estado.ELEGIDA
    p_otro.refresh_from_db()
    p_tercero.refresh_from_db()
    assert p_otro.estado == Postulacion.Estado.DESCARTADA
    assert p_tercero.estado == Postulacion.Estado.DESCARTADA
    assert {aviso.usuario for aviso in avisos()} == {elegido, otro, tercero}
    assert avisos().count() == 3
    assert "eligieron" in avisos().get(usuario=elegido).titulo
    assert "no fue elegida" in avisos().get(usuario=otro).titulo
    assert all(aviso.ficha == ficha for aviso in avisos())


def test_la_ficha_sigue_en_adopcion_y_no_se_toca_a_quienes_quieren_adoptar(carla, ficha):
    elegido = crear_hogar("lucia")
    adoptante = crear_usuario("ana")
    p_elegida = postular(elegido, ficha)
    p_adopcion = postular(adoptante, ficha, tipo=Postulacion.Tipo.ADOPCION)

    eleccion.elegir_hogar(ficha, carla, p_elegida)

    ficha.refresh_from_db()
    p_adopcion.refresh_from_db()
    assert ficha.estado == FichaAnimal.Estado.EN_ADOPCION
    assert p_adopcion.estado == Postulacion.Estado.PENDIENTE
    assert not avisos().filter(usuario=adoptante).exists()


def test_puede_elegir_un_hogar_con_el_cupo_completo(carla, ficha):
    hogar = crear_hogar("lucia", cupo_declarado=1)
    Alojamiento.objects.create(
        ficha=crear_ficha(), hogar=hogar.perfil_transito, fecha_fin_prevista=timezone.localdate()
    )
    postulacion = postular(hogar, ficha)

    assert eleccion.elegir_hogar(ficha, carla, postulacion).estado == Postulacion.Estado.ELEGIDA


def test_un_moderador_tambien_puede_elegir(ficha):
    moderador = crear_usuario("mora", rol=Rol.MODERADOR)
    postulacion = postular(crear_hogar("lucia"), ficha)

    assert eleccion.elegir_hogar(ficha, moderador, postulacion).estado == Postulacion.Estado.ELEGIDA


def test_si_quien_elige_no_puede_no_cambia_nada(ficha):
    ajeno = crear_usuario("ana")
    postulacion = postular(crear_hogar("lucia"), ficha)

    with pytest.raises(eleccion.EleccionNoPermitida):
        eleccion.elegir_hogar(ficha, ajeno, postulacion)

    postulacion.refresh_from_db()
    assert postulacion.estado == Postulacion.Estado.PENDIENTE
    assert avisos().count() == 0


def test_si_la_ficha_ya_no_esta_en_adopcion_no_se_elige(carla, ficha):
    postulacion = postular(crear_hogar("lucia"), ficha)
    FichaAnimal.objects.filter(pk=ficha.pk).update(estado=FichaAnimal.Estado.REGISTRADO)

    with pytest.raises(eleccion.EleccionNoPermitida):
        eleccion.elegir_hogar(ficha, carla, postulacion)

    postulacion.refresh_from_db()
    assert postulacion.estado == Postulacion.Estado.PENDIENTE


# Extensión 4A: el elegido ya no puede


def test_si_el_hogar_se_suspendio_no_se_elige_y_no_cambia_nada(carla, ficha):
    elegido = crear_hogar("lucia")
    otro = crear_hogar("otro")
    p_elegida = postular(elegido, ficha)
    p_otro = postular(otro, ficha)
    suspender(elegido)

    with pytest.raises(eleccion.HogarNoHabilitado):
        eleccion.elegir_hogar(ficha, carla, p_elegida)

    p_elegida.refresh_from_db()
    p_otro.refresh_from_db()
    assert p_elegida.estado == Postulacion.Estado.PENDIENTE
    assert p_otro.estado == Postulacion.Estado.PENDIENTE
    assert avisos().count() == 0


def test_si_el_hogar_se_puso_en_pausa_o_se_desactivo_no_se_elige(carla, ficha):
    en_pausa = crear_hogar("pausa")
    desactivado = crear_hogar("desactivado")
    p_pausa = postular(en_pausa, ficha)
    p_desactivado = postular(desactivado, ficha)
    PerfilTransito.objects.filter(usuario=en_pausa).update(
        disponibilidad=False, pausa_hasta=timezone.localdate() + timedelta(days=5)
    )
    PerfilTransito.objects.filter(usuario=desactivado).update(activo=False)

    with pytest.raises(eleccion.HogarNoHabilitado):
        eleccion.elegir_hogar(ficha, carla, p_pausa)
    with pytest.raises(eleccion.HogarNoHabilitado):
        eleccion.elegir_hogar(ficha, carla, p_desactivado)


def test_despues_de_un_hogar_no_habilitado_se_puede_elegir_a_otro(carla, ficha):
    suspendido = crear_hogar("suspendido")
    bueno = crear_hogar("bueno")
    p_suspendido = postular(suspendido, ficha)
    p_bueno = postular(bueno, ficha)
    suspender(suspendido)

    with pytest.raises(eleccion.HogarNoHabilitado):
        eleccion.elegir_hogar(ficha, carla, p_suspendido)
    resultado = eleccion.elegir_hogar(ficha, carla, p_bueno)

    assert resultado.estado == Postulacion.Estado.ELEGIDA
    p_suspendido.refresh_from_db()
    assert p_suspendido.estado == Postulacion.Estado.DESCARTADA


# Postulación no disponible y hogar ya elegido


def test_una_postulacion_retirada_no_se_puede_elegir(carla, ficha):
    postulacion = postular(crear_hogar("lucia"), ficha, estado=Postulacion.Estado.DESCARTADA)

    with pytest.raises(eleccion.PostulacionNoDisponible):
        eleccion.elegir_hogar(ficha, carla, postulacion)

    assert avisos().count() == 0


def test_una_postulacion_de_adopcion_o_de_otra_ficha_no_se_puede_elegir(carla, ficha):
    de_adopcion = postular(crear_hogar("ana"), ficha, tipo=Postulacion.Tipo.ADOPCION)
    de_otra = postular(crear_hogar("otra"), crear_ficha())

    with pytest.raises(eleccion.PostulacionNoDisponible):
        eleccion.elegir_hogar(ficha, carla, de_adopcion)
    with pytest.raises(eleccion.PostulacionNoDisponible):
        eleccion.elegir_hogar(ficha, carla, de_otra)


def test_con_un_hogar_ya_elegido_no_se_elige_otro(carla, ficha):
    postular(crear_hogar("elegido"), ficha, estado=Postulacion.Estado.ELEGIDA)
    nueva = postular(crear_hogar("nueva"), ficha)

    with pytest.raises(eleccion.HogarYaElegido):
        eleccion.elegir_hogar(ficha, carla, nueva)

    nueva.refresh_from_db()
    assert nueva.estado == Postulacion.Estado.PENDIENTE


def test_si_el_aviso_falla_la_eleccion_queda(carla, ficha, monkeypatch):
    def falla(*args, **kwargs):
        raise RuntimeError("falla")

    monkeypatch.setattr(eleccion, "notificar", falla)
    postulacion = postular(crear_hogar("lucia"), ficha)

    eleccion.elegir_hogar(ficha, carla, postulacion)

    postulacion.refresh_from_db()
    assert postulacion.estado == Postulacion.Estado.ELEGIDA
