"""Personas de los datos de prueba: cuentas, domicilios, perfiles y hogares de tránsito.

Los nombres son inventados y los correos usan example.com, un dominio reservado que no recibe
correo: si en la demo alguien pide recuperar la contraseña, no le llega a nadie real.
"""

import unicodedata
from dataclasses import dataclass, field
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.cuentas.models import Domicilio, EstadoCuenta, Rol, Sancion
from apps.cuentas.servicios import (
    guardar_domicilio,
    guardar_perfil_adoptante,
    sancion_vigente,
    sancionar,
)
from apps.transito.servicios import guardar_perfil_transito

from .lugares import punto


def hogar(tipo="casa", *, patio=False, convivientes=2, ninos=False, mascotas=0):
    """Los datos del hogar del domicilio (los que pide el perfil de hogar y familia)."""
    return {
        "tipo_vivienda": tipo,
        "tiene_patio": patio,
        "convivientes": convivientes,
        "hay_ninos": ninos,
        "mascotas_propias": mascotas,
    }


def transito(especies, tamano, dias, cupo, *, medicacion=False, conducta=False, pausa_dias=0):
    """El perfil de hogar de tránsito. Con "pausa_dias" queda en pausa esos días."""
    return {
        "especies": especies,
        "tamano_maximo": tamano,
        "duracion_maxima_dias": dias,
        "cupo_declarado": cupo,
        "acepta_medicacion": medicacion,
        "acepta_conducta": conducta,
        "pausa_dias": pausa_dias,
    }


@dataclass(frozen=True)
class Persona:
    nombre: str
    lugar: str = ""  # clave de LUGARES; sin lugar, la cuenta no tiene domicilio
    vivienda: dict = field(default_factory=hogar)
    experiencia: str = ""  # con experiencia, tiene perfil de hogar y familia (adoptante)
    transito: dict | None = None
    rol: str = Rol.REGISTRADO
    estado: str = EstadoCuenta.ACTIVA
    sancion: str = ""  # tipo de Sancion; la aplica la moderadora
    motivo: str = ""

    @property
    def email(self):
        sin_tildes = unicodedata.normalize("NFKD", self.nombre).encode("ascii", "ignore")
        return sin_tildes.decode().lower().replace(" ", ".") + "@example.com"


PERRO_Y_GATO = ["perro", "gato"]

PERSONAS = {
    # Moderación
    "gabriela": Persona("Gabriela Ortiz", "centro", rol=Rol.MODERADOR),
    # Hogares de tránsito, cada uno en una situación distinta
    "lucia": Persona(
        "Lucía Fernández",
        "kaupen",
        hogar(patio=True, convivientes=3, mascotas=1),
        transito=transito(PERRO_Y_GATO, "grande", 90, 4, medicacion=True, conducta=True),
    ),
    "martin": Persona(
        "Martín Gómez",
        "calafate",
        hogar("departamento", convivientes=1),
        transito=transito(["gato"], "pequeno", 30, 1),
    ),
    "romina": Persona(
        "Romina Sosa",
        "los_morros",
        hogar(convivientes=4, ninos=True, mascotas=2),
        experiencia="Siempre tuvimos perros y gatos; los chicos están acostumbrados.",
        transito=transito(PERRO_Y_GATO, "mediano", 60, 2, medicacion=True),
    ),
    "tomas": Persona(
        "Tomás Aguirre",
        "andino",
        hogar(patio=True),
        transito=transito(PERRO_Y_GATO, "grande", 120, 2, conducta=True, pausa_dias=30),
    ),
    "valeria": Persona(
        "Valeria Ríos",
        "pedro_fique",
        hogar(mascotas=1),
        transito=transito(PERRO_Y_GATO, "grande", 60, 2, medicacion=True),
        sancion=Sancion.Tipo.TEMPORAL,
        motivo="Dejó un teléfono falso en una postulación.",
    ),
    "diego": Persona(
        "Diego Paredes",
        "las_reinas",
        hogar(patio=True, convivientes=1),
        transito=transito(["perro"], "grande", 45, 1),
    ),
    # Quieren adoptar
    "ana": Persona(
        "Ana Benítez",
        "alto_ecologico",
        hogar(patio=True),
        experiencia="Tuve perros toda la vida. El último vivió 15 años.",
    ),
    "carla": Persona(
        "Carla Medina",
        "mision_alta",
        hogar("departamento", convivientes=1, mascotas=1),
        experiencia="Tengo una gata de 4 años y quiero sumar otra.",
    ),
    "federico": Persona(
        "Federico Luna",
        "bahia_golondrina",
        hogar(patio=True, convivientes=4, ninos=True),
        experiencia="Es nuestra primera mascota. Los chicos la piden hace años.",
    ),
    "paula": Persona(
        "Paula Castro",
        "mirador_beagle",
        hogar("departamento", convivientes=2),
        experiencia="De chica tuve gatos en la casa de mis viejos.",
    ),
    # Dueños, vecinos que encuentran animales y rescatistas
    "sofia": Persona("Sofía Herrera", "el_mirador", hogar(convivientes=3, mascotas=1)),
    "joaquin": Persona("Joaquín Peralta", "tolkar", hogar("departamento", convivientes=2)),
    "camila": Persona("Camila Vera", "peron", hogar("departamento", convivientes=1)),
    "emanuel": Persona("Emanuel Díaz", "ara_belgrano", hogar(patio=True, mascotas=2)),
    "nicolas": Persona("Nicolás Acosta", "los_pinos", hogar(patio=True, convivientes=3)),
    "florencia": Persona("Florencia Molina", "la_cantera", hogar(ninos=True, convivientes=4)),
    "sebastian": Persona("Sebastián Rojas", "rio_pipo", hogar(patio=True, mascotas=1)),
    "julieta": Persona("Julieta Navarro", "siete_cascadas", hogar(patio=True)),
    "matias": Persona("Matías Suárez", "el_libertador", hogar(convivientes=5, ninos=True)),
    "agustina": Persona("Agustina Cabrera", "parque", hogar("departamento", convivientes=1)),
    # Cuentas en otros estados
    "bruno": Persona("Bruno Méndez", estado=EstadoCuenta.PENDIENTE),
    "marcos": Persona(
        "Marcos Villalba",
        "jose_hernandez",
        sancion=Sancion.Tipo.PERMANENTE,
        motivo="Publicó varias veces avisos falsos para vender animales.",
    ),
}


@transaction.atomic
def cargar_personas(password):
    """Crea (o actualiza) las cuentas y devuelve {clave: usuario}."""
    usuarios = {clave: _cuenta(persona, password) for clave, persona in PERSONAS.items()}
    moderadora = usuarios["gabriela"]
    for clave, persona in PERSONAS.items():
        if persona.sancion and sancion_vigente(usuarios[clave]) is None:
            sancionar(usuarios[clave], persona.sancion, persona.motivo, moderadora)
    return usuarios


def _cuenta(persona, password):
    modelo = get_user_model()
    usuario = modelo.objects.filter(email=persona.email).first()
    if usuario is None:
        usuario = modelo.objects.create_user(
            persona.email,
            persona.nombre,
            password,
            rol=persona.rol,
            estado_cuenta=persona.estado,
        )
    if persona.lugar:
        guardar_domicilio(usuario, punto(persona.lugar))
        Domicilio.objects.filter(usuario=usuario).update(**persona.vivienda)
    if persona.experiencia:
        guardar_perfil_adoptante(usuario, persona.experiencia)
    if persona.transito:
        _hogar_de_transito(usuario, persona.transito)
    return usuario


def _hogar_de_transito(usuario, datos):
    perfil = dict(datos)
    pausa_dias = perfil.pop("pausa_dias")
    perfil["disponibilidad"] = not pausa_dias
    if pausa_dias:
        perfil["pausa_hasta"] = timezone.localdate() + timedelta(days=pausa_dias)
    guardar_perfil_transito(usuario, **perfil)
