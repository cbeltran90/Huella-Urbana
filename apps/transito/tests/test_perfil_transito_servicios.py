from datetime import timedelta

import pytest
from constance import config
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.cuentas.models import Domicilio, EstadoCuenta, Usuario
from apps.transito import servicios
from apps.transito.models import MAX_CUPO_DECLARADO, PerfilTransito

CLAVE = "clave-de-prueba-1"


@pytest.fixture
def ana():
    return Usuario.objects.create_user(
        "ana@example.com", "Ana", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )


def dar_domicilio(usuario, **hogar):
    datos = {
        "tipo_vivienda": "casa",
        "tiene_patio": True,
        "convivientes": 2,
        "hay_ninos": False,
        "mascotas_propias": 1,
        **hogar,
    }
    return Domicilio.objects.create(
        usuario=usuario,
        ubicacion=Point(-68.30, -54.80, srid=4326),
        ubicacion_desplazada=Point(-68.301, -54.801, srid=4326),
        **datos,
    )


@pytest.fixture
def ana_con_hogar(ana):
    dar_domicilio(ana)
    return ana


def datos(**cambios):
    base = {
        "especies": ["perro", "gato"],
        "tamano_maximo": "mediano",
        "duracion_maxima_dias": 30,
        "disponibilidad": True,
        "cupo_declarado": 2,
    }
    return {**base, **cambios}


def manana():
    return timezone.localdate() + timedelta(days=1)


@pytest.mark.django_db
def test_con_todo_en_orden_guarda_y_activa_el_perfil(ana_con_hogar):
    perfil = servicios.guardar_perfil_transito(ana_con_hogar, **datos())

    assert perfil.usuario == ana_con_hogar
    assert perfil.activo is True
    assert perfil.especies == ["perro", "gato"]
    assert perfil.tamano_maximo == "mediano"
    assert perfil.duracion_maxima_dias == 30
    assert perfil.cupo_declarado == 2
    assert servicios.es_hogar_de_transito(ana_con_hogar) is True


@pytest.mark.django_db
def test_guarda_las_opciones_de_medicacion_y_conducta(ana_con_hogar):
    perfil = servicios.guardar_perfil_transito(
        ana_con_hogar, **datos(acepta_medicacion=True, acepta_conducta=True)
    )

    assert perfil.acepta_medicacion is True
    assert perfil.acepta_conducta is True


@pytest.mark.django_db
def test_las_especies_se_guardan_ordenadas_y_sin_repetidos(ana_con_hogar):
    perfil = servicios.guardar_perfil_transito(
        ana_con_hogar, **datos(especies=["gato", "perro", "gato"])
    )

    assert perfil.especies_aceptadas == "perro,gato"


@pytest.mark.django_db
def test_sin_domicilio_pide_los_datos_del_hogar_y_no_guarda(ana):
    with pytest.raises(servicios.HogarIncompleto) as error:
        servicios.guardar_perfil_transito(ana, **datos())

    assert "Domicilio" in error.value.faltantes
    assert "Personas con las que convive" in error.value.faltantes
    assert not PerfilTransito.objects.exists()


@pytest.mark.django_db
def test_con_el_hogar_a_medias_dice_cuales_faltan(ana):
    dar_domicilio(ana, tiene_patio=None, convivientes=None)

    with pytest.raises(servicios.HogarIncompleto) as error:
        servicios.guardar_perfil_transito(ana, **datos())

    assert len(error.value.faltantes) == 2
    assert error.value.faltantes == ["Patio", "Personas con las que convive"]
    assert not PerfilTransito.objects.exists()


@pytest.mark.django_db
def test_el_cero_y_el_no_cuentan_como_respuestas_del_hogar(ana):
    dar_domicilio(ana, tiene_patio=False, convivientes=0, hay_ninos=False, mascotas_propias=0)

    servicios.guardar_perfil_transito(ana, **datos())

    assert PerfilTransito.objects.filter(usuario=ana).exists()


@pytest.mark.django_db
def test_sin_campos_obligatorios_no_guarda_y_dice_que_falta(ana_con_hogar):
    with pytest.raises(servicios.PerfilTransitoIncompleto) as error:
        servicios.guardar_perfil_transito(
            ana_con_hogar,
            **datos(
                especies=[],
                tamano_maximo="",
                duracion_maxima_dias=None,
                disponibilidad=None,
                cupo_declarado=None,
            ),
        )

    assert error.value.faltantes == [
        servicios.ETIQUETA_ESPECIES,
        servicios.ETIQUETA_TAMANO,
        servicios.ETIQUETA_DURACION,
        servicios.ETIQUETA_DISPONIBILIDAD,
        servicios.ETIQUETA_CUPO,
    ]
    assert not PerfilTransito.objects.exists()
    assert servicios.es_hogar_de_transito(ana_con_hogar) is False


@pytest.mark.django_db
def test_en_pausa_sin_fecha_de_reanudacion_falta_la_fecha(ana_con_hogar):
    with pytest.raises(servicios.PerfilTransitoIncompleto) as error:
        servicios.guardar_perfil_transito(ana_con_hogar, **datos(disponibilidad=False))

    assert error.value.faltantes == [servicios.ETIQUETA_REANUDACION]


@pytest.mark.django_db
def test_la_duracion_menor_a_la_minima_muestra_el_mensaje(ana_con_hogar):
    with pytest.raises(servicios.PerfilTransitoInvalido) as error:
        servicios.guardar_perfil_transito(ana_con_hogar, **datos(duracion_maxima_dias=6))

    assert error.value.errores == {"duracion_maxima_dias": "La duración mínima es de 7 días"}
    assert not PerfilTransito.objects.exists()


@pytest.mark.django_db
def test_la_duracion_minima_justa_es_valida(ana_con_hogar):
    servicios.guardar_perfil_transito(ana_con_hogar, **datos(duracion_maxima_dias=7))


@pytest.mark.django_db
def test_la_duracion_minima_sale_del_parametro(ana_con_hogar):
    config.DURACION_MINIMA_TRANSITO_DIAS = 10

    with pytest.raises(servicios.PerfilTransitoInvalido) as error:
        servicios.guardar_perfil_transito(ana_con_hogar, **datos(duracion_maxima_dias=9))

    assert error.value.errores == {"duracion_maxima_dias": "La duración mínima es de 10 días"}


@pytest.mark.django_db
def test_la_duracion_no_puede_superar_el_tope(ana_con_hogar):
    with pytest.raises(servicios.PerfilTransitoInvalido) as error:
        servicios.guardar_perfil_transito(
            ana_con_hogar,
            **datos(duracion_maxima_dias=servicios.MAX_DURACION_MAXIMA_DIAS + 1),
        )

    assert error.value.errores == {"duracion_maxima_dias": servicios.MENSAJE_DURACION_LARGA}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("cambio", "campo"),
    [
        ({"especies": ["dragon"]}, "especies"),
        ({"tamano_maximo": "gigante"}, "tamano_maximo"),
        ({"cupo_declarado": 0}, "cupo_declarado"),
        ({"cupo_declarado": MAX_CUPO_DECLARADO + 1}, "cupo_declarado"),
    ],
)
def test_los_valores_invalidos_no_se_guardan(ana_con_hogar, cambio, campo):
    with pytest.raises(servicios.PerfilTransitoInvalido) as error:
        servicios.guardar_perfil_transito(ana_con_hogar, **datos(**cambio))

    assert set(error.value.errores) == {campo}
    assert not PerfilTransito.objects.exists()


@pytest.mark.django_db
def test_en_pausa_guarda_la_fecha_de_reanudacion(ana_con_hogar):
    perfil = servicios.guardar_perfil_transito(
        ana_con_hogar, **datos(disponibilidad=False, pausa_hasta=manana())
    )

    assert perfil.disponibilidad is False
    assert perfil.pausa_hasta == manana()


@pytest.mark.django_db
@pytest.mark.parametrize("dias", [0, -3])
def test_la_fecha_de_reanudacion_tiene_que_ser_futura(ana_con_hogar, dias):
    fecha = timezone.localdate() + timedelta(days=dias)

    with pytest.raises(servicios.PerfilTransitoInvalido) as error:
        servicios.guardar_perfil_transito(
            ana_con_hogar, **datos(disponibilidad=False, pausa_hasta=fecha)
        )

    assert error.value.errores == {"pausa_hasta": servicios.MENSAJE_PAUSA_PASADA}


@pytest.mark.django_db
def test_disponible_borra_la_fecha_de_pausa(ana_con_hogar):
    perfil = servicios.guardar_perfil_transito(
        ana_con_hogar, **datos(disponibilidad=True, pausa_hasta=manana())
    )

    assert perfil.pausa_hasta is None


@pytest.mark.django_db
def test_guardar_de_nuevo_actualiza_el_mismo_perfil(ana_con_hogar):
    servicios.guardar_perfil_transito(ana_con_hogar, **datos())

    servicios.guardar_perfil_transito(ana_con_hogar, **datos(cupo_declarado=4, especies=["gato"]))

    assert PerfilTransito.objects.count() == 1
    perfil = PerfilTransito.objects.get()
    assert perfil.cupo_declarado == 4
    assert perfil.especies == ["gato"]


@pytest.mark.django_db
def test_guardar_reactiva_un_perfil_desactivado(ana_con_hogar):
    servicios.guardar_perfil_transito(ana_con_hogar, **datos())
    PerfilTransito.objects.update(activo=False)

    servicios.guardar_perfil_transito(ana_con_hogar, **datos())

    assert servicios.es_hogar_de_transito(ana_con_hogar) is True


@pytest.mark.django_db
def test_un_error_al_actualizar_deja_el_perfil_como_estaba(ana_con_hogar):
    servicios.guardar_perfil_transito(ana_con_hogar, **datos())

    with pytest.raises(servicios.PerfilTransitoInvalido):
        servicios.guardar_perfil_transito(ana_con_hogar, **datos(cupo_declarado=0))

    assert PerfilTransito.objects.get().cupo_declarado == 2


def perfil_en_memoria(**campos):
    return PerfilTransito(**{"activo": True, "disponibilidad": True, "pausa_hasta": None, **campos})


def test_disponible_esta_disponible():
    assert servicios.esta_disponible(perfil_en_memoria()) is True


def test_en_pausa_no_esta_disponible_antes_de_la_fecha():
    hoy = timezone.localdate()
    perfil = perfil_en_memoria(disponibilidad=False, pausa_hasta=hoy + timedelta(days=1))

    assert servicios.esta_disponible(perfil, hoy=hoy) is False


def test_al_llegar_la_fecha_de_reanudacion_vuelve_a_estar_disponible():
    hoy = timezone.localdate()
    perfil = perfil_en_memoria(disponibilidad=False, pausa_hasta=hoy)

    assert servicios.esta_disponible(perfil, hoy=hoy) is True


def test_un_perfil_desactivado_nunca_esta_disponible():
    assert servicios.esta_disponible(perfil_en_memoria(activo=False)) is False
