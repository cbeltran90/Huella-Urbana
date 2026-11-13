from datetime import timedelta

import pytest
from django.utils import timezone

from apps.cuentas.models import EstadoCuenta, Rol, Sancion, Usuario
from apps.cuentas.servicios import sancionar
from apps.fichas.models import FichaAnimal
from apps.transito import servicios
from apps.transito.models import PerfilTransito

CLAVE = "clave-de-prueba-1"


def hogar(nombre, **perfil):
    usuario = Usuario.objects.create_user(
        f"{nombre}@example.com", nombre.title(), CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    datos = {
        "especies_aceptadas": "perro,gato",
        "tamano_maximo": "grande",
        "duracion_maxima_dias": 30,
        "cupo_declarado": 2,
        **perfil,
    }
    return PerfilTransito.objects.create(usuario=usuario, **datos)


def ficha(**campos):
    datos = {"especie": "perro", "tamano": "mediano", **campos}
    return FichaAnimal.objects.create(**datos)


# Hogares compatibles (a quienes se avisa, CU-17)


@pytest.mark.django_db
def test_un_hogar_que_encaja_aparece():
    perfil = hogar("ana")

    assert servicios.hogares_compatibles(ficha()) == [perfil]


@pytest.mark.django_db
def test_devuelve_perfiles_con_su_usuario_ordenados():
    primero = hogar("ana")
    segundo = hogar("beto")

    resultado = servicios.hogares_compatibles(ficha())

    assert resultado == [primero, segundo]
    assert [perfil.usuario.email for perfil in resultado] == [
        "ana@example.com",
        "beto@example.com",
    ]


@pytest.mark.django_db
def test_sin_hogares_la_lista_esta_vacia():
    assert servicios.hogares_compatibles(ficha()) == []


@pytest.mark.django_db
def test_no_aparece_un_hogar_que_no_acepta_la_especie():
    hogar("ana", especies_aceptadas="gato")

    assert servicios.hogares_compatibles(ficha(especie="perro")) == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("tamano_animal", "tamano_hogar", "aparece"),
    [
        ("pequeno", "mediano", True),
        ("mediano", "mediano", True),
        ("grande", "mediano", False),
        ("mediano", "pequeno", False),
        ("grande", "grande", True),
    ],
)
def test_el_tamano_del_animal_no_puede_superar_el_maximo_del_hogar(
    tamano_animal, tamano_hogar, aparece
):
    perfil = hogar("ana", tamano_maximo=tamano_hogar)

    resultado = servicios.hogares_compatibles(ficha(tamano=tamano_animal))

    assert (perfil in resultado) is aparece


@pytest.mark.django_db
def test_si_la_ficha_no_tiene_tamano_el_hogar_no_se_descarta():
    perfil = hogar("ana", tamano_maximo="pequeno")

    assert servicios.hogares_compatibles(ficha(tamano="")) == [perfil]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("requiere", "acepta", "aparece"),
    [(True, False, False), (True, True, True), (False, False, True), (False, True, True)],
)
def test_la_medicacion_se_cruza_con_lo_que_acepta_el_hogar(requiere, acepta, aparece):
    perfil = hogar("ana", acepta_medicacion=acepta)

    resultado = servicios.hogares_compatibles(ficha(requiere_medicacion=requiere))

    assert (perfil in resultado) is aparece


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("problemas", "acepta", "aparece"),
    [(True, False, False), (True, True, True), (False, False, True), (False, True, True)],
)
def test_la_conducta_se_cruza_con_lo_que_acepta_el_hogar(problemas, acepta, aparece):
    perfil = hogar("ana", acepta_conducta=acepta)

    resultado = servicios.hogares_compatibles(ficha(problemas_conducta=problemas))

    assert (perfil in resultado) is aparece


@pytest.mark.django_db
def test_no_aparece_un_hogar_en_pausa_hasta_que_vuelve():
    hoy = timezone.localdate()
    perfil = hogar("ana", disponibilidad=False, pausa_hasta=hoy + timedelta(days=3))

    assert servicios.hogares_compatibles(ficha(), hoy=hoy) == []
    assert servicios.hogares_compatibles(ficha(), hoy=hoy + timedelta(days=3)) == [perfil]


@pytest.mark.django_db
def test_no_aparece_un_perfil_desactivado():
    hogar("ana", activo=False)

    assert servicios.hogares_compatibles(ficha()) == []


@pytest.mark.django_db
def test_no_aparece_un_hogar_con_la_cuenta_suspendida():
    perfil = hogar("ana")
    moderadora = Usuario.objects.create_user(
        "mod@example.com", "Mod", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA, rol=Rol.MODERADOR
    )
    sancionar(perfil.usuario, Sancion.Tipo.TEMPORAL, "Motivo", moderadora)

    assert servicios.hogares_compatibles(ficha()) == []


@pytest.mark.django_db
def test_no_aparece_un_hogar_con_la_cuenta_sin_confirmar():
    perfil = hogar("ana")
    Usuario.objects.filter(pk=perfil.usuario.pk).update(estado_cuenta=EstadoCuenta.PENDIENTE)

    assert servicios.hogares_compatibles(ficha()) == []


@pytest.mark.django_db
def test_el_cupo_completo_no_descarta_a_un_hogar(monkeypatch):
    perfil = hogar("ana", cupo_declarado=2)
    monkeypatch.setattr(servicios, "animales_alojados", lambda usuario: 2)

    assert servicios.hogares_compatibles(ficha()) == [perfil]


# Aviso de incompatibilidad (CU-24 3B y CU-25)


@pytest.mark.django_db
def test_sin_incompatibilidades_cuando_el_hogar_encaja():
    assert servicios.incompatibilidades(hogar("ana"), ficha()) == []


@pytest.mark.django_db
def test_los_motivos_se_acumulan_en_orden():
    perfil = hogar("ana", especies_aceptadas="gato", tamano_maximo="pequeno")
    animal = ficha(
        especie="perro", tamano="grande", requiere_medicacion=True, problemas_conducta=True
    )

    assert servicios.incompatibilidades(perfil, animal) == [
        servicios.MOTIVO_ESPECIE,
        servicios.MOTIVO_TAMANO,
        servicios.MOTIVO_MEDICACION,
        servicios.MOTIVO_CONDUCTA,
    ]


@pytest.mark.django_db
def test_un_hogar_incompatible_sigue_habilitado_para_postularse():
    perfil = hogar("ana", especies_aceptadas="gato")

    assert servicios.incompatibilidades(perfil, ficha(especie="perro")) != []
    assert servicios.hogar_habilitado(perfil) is True


@pytest.mark.django_db
def test_sin_tamano_en_la_ficha_no_hay_incompatibilidad_de_tamano():
    perfil = hogar("ana", tamano_maximo="pequeno")

    assert servicios.incompatibilidades(perfil, ficha(tamano="")) == []


@pytest.mark.django_db
def test_devuelve_perfiles_con_su_usuario():
    perfil = hogar("ana")

    resultado = servicios.hogares_compatibles(ficha())

    assert resultado == [perfil]
    assert resultado[0].usuario.email == "ana@example.com"
