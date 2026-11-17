"""Lugares de Ushuaia para los datos de prueba.

Cada punto está sobre una calle real (OpenStreetMap) y a 250 m o más de la costa, de la
Bahía Encerrada y de las lagunas. Así, aunque el punto de un domicilio se desplace (hasta
RADIO_DOMICILIO_METROS, 150 m), no cae al agua.
"""

from typing import NamedTuple

from django.contrib.gis.geos import Point


class Lugar(NamedTuple):
    barrio: str
    calle: str
    lon: float
    lat: float


LUGARES = {
    # Centro y laderas
    "centro": Lugar("Centro", "Juan Manuel de Rosas", -68.31129, -54.80670),
    "calafate": Lugar("Calafate", "25 de Mayo", -68.30906, -54.80350),
    "peron": Lugar("Perón", "Gobernador José María Gómez", -68.30891, -54.80000),
    "peron_alto": Lugar("Perón", "Antártida Argentina", -68.30444, -54.79901),
    "ara_belgrano": Lugar("ARA General Belgrano", "Ramón Barrios", -68.30032, -54.80234),
    "itulara": Lugar("Itulara", "Hol Hol", -68.31772, -54.80092),
    "mirador_beagle": Lugar("Mirador del Beagle", "Isla Redonda Este", -68.31068, -54.79528),
    "mirador_beagle_alto": Lugar("Mirador del Beagle", "Las Raíces", -68.30887, -54.79358),
    # Este
    "alto_ecologico": Lugar("Alto Ecológico", "Las Violetas", -68.29850, -54.79833),
    "alto_ecologico_este": Lugar("Alto Ecológico", "Bahía Buen Suceso", -68.29276, -54.79508),
    "kaiken": Lugar("Kaikén", "Vinciguerra", -68.29665, -54.78689),
    "siete_cascadas": Lugar("7 Cascadas", "Cortez", -68.29251, -54.78066),
    "parque": Lugar("Parque", "44 Héroes ARA San Juan", -68.28834, -54.79971),
    "canadon_del_parque": Lugar("Cañadón del Parque", "Raúl Muriel", -68.28966, -54.79768),
    "los_morros": Lugar("Los Morros", "Juan Facundo Quiroga", -68.28308, -54.79622),
    "los_morros_alto": Lugar("Los Morros", "Ñire", -68.28025, -54.79356),
    "las_reinas": Lugar("Las Reinas", "Camino del Valle", -68.28027, -54.78772),
    "la_cantera": Lugar("La Cantera", "Eva Perón", -68.27335, -54.78953),
    "el_mirador": Lugar("El Mirador", "Puerto Remolino", -68.24786, -54.79126),
    "pedro_fique": Lugar("Pedro Fique", "José Cabezas", -68.23581, -54.79255),
    # Oeste
    "mision_baja": Lugar("Misión Baja", "Capitán Armando Mutto", -68.30990, -54.81765),
    "mision_alta": Lugar("Misión Alta", "Suboficial Nelson Villagra", -68.32353, -54.82021),
    "tolkar": Lugar("Tolkar", "Robert Fitz Roy", -68.32399, -54.81601),
    "las_lengas": Lugar("Las Lengas", "Goleta Florencia", -68.32303, -54.81114),
    "penaloza": Lugar("Peñaloza", "Pasaje del Técnico", -68.32370, -54.80892),
    "kaupen": Lugar("Kaupén", "Cilawaia", -68.32941, -54.80432),
    "jose_hernandez": Lugar("José Hernández", "Olegario Andrade", -68.32570, -54.81095),
    "almirante_brown": Lugar("Almirante Brown", "Damiana F. de Fique", -68.33155, -54.81487),
    "el_fuelle": Lugar("El Fuelle", "1 de Mayo", -68.32695, -54.82003),
    "san_salvador": Lugar("San Salvador", "Juan Rodríguez", -68.32930, -54.82436),
    "los_pinos": Lugar("Los Pinos", "Crucero General Belgrano", -68.33432, -54.81045),
    "el_libertador": Lugar("El Libertador", "Ceferino Namuncurá", -68.33931, -54.81899),
    "bahia_golondrina": Lugar("Bahía Golondrina", "Isla San Pedro", -68.33804, -54.82602),
    "malvinas": Lugar("Malvinas Argentinas", "Isla Soledad", -68.33894, -54.83012),
    "onaisin": Lugar("Onaisín", "Aldo Motter", -68.34057, -54.80820),
    "andino": Lugar("Andino", "Las Vertientes", -68.34670, -54.81560),
    "fueguino": Lugar("Fueguino", "Isla San Pedro", -68.34302, -54.82158),
    "costas_del_sur": Lugar("Costas del Sur", "Del Tolkeyén", -68.34619, -54.82892),
    "rio_pipo": Lugar("Río Pipo", "Entre Ríos", -68.35469, -54.82469),
    "alacalufes": Lugar("Los Alacalufes", "Neuquén", -68.35672, -54.82016),
    "bella_vista": Lugar("Bella Vista", "De la Estancia", -68.36602, -54.83230),
}


def punto(clave):
    """El punto del lugar como Point de GeoDjango (SRID 4326)."""
    lugar = LUGARES[clave]
    return Point(lugar.lon, lugar.lat, srid=4326)
