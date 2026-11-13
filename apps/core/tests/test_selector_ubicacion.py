from django.contrib.staticfiles import finders
from django.template.loader import render_to_string

CONFIG = {"tiles_url": "https://ejemplo.test/{z}/{x}/{y}.png", "atribucion": "Prueba"}


def test_el_javascript_del_selector_esta_en_los_estaticos():
    assert finders.find("js/selector_ubicacion.js") is not None


def test_el_marcado_trae_el_boton_el_mapa_y_los_campos():
    html = render_to_string("componentes/_selector_ubicacion.html", {"mapa_id": "mapa-prueba"})

    assert 'id="mapa-prueba"' in html
    assert 'id="boton-gps"' in html
    assert 'name="latitud"' in html
    assert 'name="longitud"' in html


def test_el_script_inicia_el_selector_sobre_el_mapa_indicado():
    html = render_to_string(
        "componentes/_selector_ubicacion_js.html",
        {"mapa_id": "mapa-prueba", "mapa_config": CONFIG},
    )

    assert "js/selector_ubicacion.js" in html
    assert 'SelectorUbicacion.iniciar("mapa-prueba")' in html
    assert 'id="mapa-config"' in html
    assert 'id="mapa-centro"' not in html


def test_si_hay_un_centro_lo_ofrece_al_selector():
    html = render_to_string(
        "componentes/_selector_ubicacion_js.html",
        {
            "mapa_id": "mapa-prueba",
            "mapa_config": CONFIG,
            "centro": {"lat": -54.8, "lng": -68.3},
        },
    )

    assert 'id="mapa-centro"' in html
