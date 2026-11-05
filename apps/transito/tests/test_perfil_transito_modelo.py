import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError

from apps.cuentas.models import EstadoCuenta, Rol, Usuario
from apps.fichas.models import FichaAnimal
from apps.transito import servicios
from apps.transito.models import MAX_CUPO_DECLARADO, PerfilTransito

CLAVE = "clave-de-prueba-1"


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def crear(usuario, **campos):
    datos = {
        "especies_aceptadas": "perro,gato",
        "tamano_maximo": "mediano",
        "duracion_maxima_dias": 30,
        "cupo_declarado": 3,
        **campos,
    }
    return PerfilTransito.objects.create(usuario=usuario, **datos)


@pytest.mark.django_db
def test_se_guarda_y_se_accede_desde_el_usuario(ana):
    perfil = crear(ana)

    assert ana.perfil_transito == perfil
    assert perfil.pk == ana.pk


@pytest.mark.django_db
def test_los_valores_por_defecto(ana):
    perfil = crear(ana)

    assert perfil.activo is True
    assert perfil.disponibilidad is True
    assert perfil.pausa_hasta is None
    assert perfil.acepta_medicacion is False
    assert perfil.acepta_conducta is False


@pytest.mark.django_db
def test_las_especies_se_leen_como_lista(ana):
    assert crear(ana, especies_aceptadas="perro,gato").especies == ["perro", "gato"]
    assert crear(
        Usuario.objects.create_user("b@example.com", "Beto", CLAVE),
        especies_aceptadas="gato",
    ).especies == ["gato"]


def test_sin_especies_la_lista_esta_vacia():
    assert PerfilTransito(especies_aceptadas="").especies == []


def test_los_tamanos_son_los_de_la_ficha_de_animal():
    campo = PerfilTransito._meta.get_field("tamano_maximo")

    assert campo.choices == FichaAnimal.Tamano.choices


@pytest.mark.django_db
def test_un_perfil_valido_pasa_la_validacion(ana):
    crear(ana).full_clean()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "invalido",
    [
        {"tamano_maximo": "gigante"},
        {"cupo_declarado": 0},
        {"cupo_declarado": MAX_CUPO_DECLARADO + 1},
        {"especies_aceptadas": ""},
    ],
)
def test_un_valor_invalido_no_pasa_la_validacion(ana, invalido):
    perfil = crear(ana)
    for campo, valor in invalido.items():
        setattr(perfil, campo, valor)

    with pytest.raises(ValidationError) as error:
        perfil.full_clean()

    assert set(error.value.message_dict) == set(invalido)


@pytest.mark.django_db
def test_borrar_la_cuenta_borra_el_perfil(ana):
    crear(ana)

    ana.delete()

    assert not PerfilTransito.objects.exists()


@pytest.mark.django_db
def test_con_un_perfil_activo_es_hogar_de_transito(ana):
    crear(ana)

    assert servicios.es_hogar_de_transito(ana) is True


@pytest.mark.django_db
def test_con_el_perfil_desactivado_ya_no_es_hogar_de_transito(ana):
    crear(ana, activo=False)

    assert servicios.es_hogar_de_transito(ana) is False


@pytest.mark.django_db
def test_sin_perfil_no_es_hogar_de_transito(ana):
    assert servicios.es_hogar_de_transito(ana) is False


def test_un_visitante_no_es_hogar_de_transito():
    assert servicios.es_hogar_de_transito(AnonymousUser()) is False


@pytest.mark.django_db
def test_el_rol_de_la_cuenta_no_cambia(ana):
    crear(ana)

    ana.refresh_from_db()
    assert ana.rol == Rol.REGISTRADO
    assert ana.is_staff is False
