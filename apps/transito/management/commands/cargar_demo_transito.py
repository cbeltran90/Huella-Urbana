"""Datos de prueba de la demo de hogares de tránsito.

Deja cinco hogares con situaciones distintas (habilitado en cada caso, en pausa y suspendido),
un moderador y a Bruno, un perro grande que necesita medicación. Con eso se ve cuáles hogares
se habilitan y a cuáles se les avisaría por Bruno.
Se puede correr las veces que haga falta: no duplica nada.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.cuentas.models import Domicilio, EstadoCuenta, Rol, Sancion
from apps.cuentas.servicios import guardar_domicilio, sancion_vigente, sancionar
from apps.fichas.models import FichaAnimal
from apps.fichas.servicios import crear_ficha_sin_responsable
from apps.transito import servicios
from apps.transito.models import PerfilTransito

MODERADOR = ("moderador@demo.huella.test", "moderador_demo", (-68.3100, -54.8000))

# Cada hogar: correo, nombre de usuario, domicilio (longitud, latitud), datos de la vivienda
# y perfil de tránsito. "pausa_dias" pone al hogar en pausa esa cantidad de días.
HOGARES = {
    "lucia": {
        "email": "lucia@demo.huella.test",
        "nombre_usuario": "lucia_demo",
        "punto": (-68.2900, -54.8150),
        "vivienda": {
            "tipo_vivienda": "casa",
            "tiene_patio": True,
            "convivientes": 3,
            "hay_ninos": False,
            "mascotas_propias": 1,
        },
        "perfil": {
            "especies": ["perro", "gato"],
            "tamano_maximo": "grande",
            "duracion_maxima_dias": 90,
            "cupo_declarado": 4,
            "acepta_medicacion": True,
            "acepta_conducta": True,
        },
    },
    "martin": {
        "email": "martin@demo.huella.test",
        "nombre_usuario": "martin_demo",
        "punto": (-68.3050, -54.8070),
        "vivienda": {
            "tipo_vivienda": "departamento",
            "tiene_patio": False,
            "convivientes": 1,
            "hay_ninos": False,
            "mascotas_propias": 0,
        },
        "perfil": {
            "especies": ["gato"],
            "tamano_maximo": "pequeno",
            "duracion_maxima_dias": 30,
            "cupo_declarado": 1,
        },
    },
    "romina": {
        "email": "romina@demo.huella.test",
        "nombre_usuario": "romina_demo",
        "punto": (-68.2750, -54.8120),
        "vivienda": {
            "tipo_vivienda": "casa",
            "tiene_patio": False,
            "convivientes": 4,
            "hay_ninos": True,
            "mascotas_propias": 2,
        },
        "perfil": {
            "especies": ["perro", "gato"],
            "tamano_maximo": "mediano",
            "duracion_maxima_dias": 60,
            "cupo_declarado": 2,
            "acepta_medicacion": True,
        },
    },
    "tomas": {
        "email": "tomas@demo.huella.test",
        "nombre_usuario": "tomas_demo",
        "punto": (-68.2850, -54.8030),
        "vivienda": {
            "tipo_vivienda": "casa",
            "tiene_patio": True,
            "convivientes": 2,
            "hay_ninos": False,
            "mascotas_propias": 0,
        },
        "perfil": {
            "especies": ["perro", "gato"],
            "tamano_maximo": "grande",
            "duracion_maxima_dias": 120,
            "cupo_declarado": 2,
            "acepta_medicacion": True,
            "acepta_conducta": True,
            "pausa_dias": 30,
        },
    },
    "valeria": {
        "email": "valeria@demo.huella.test",
        "nombre_usuario": "valeria_demo",
        "punto": (-68.3000, -54.8180),
        "vivienda": {
            "tipo_vivienda": "casa",
            "tiene_patio": False,
            "convivientes": 2,
            "hay_ninos": False,
            "mascotas_propias": 1,
        },
        "perfil": {
            "especies": ["perro", "gato"],
            "tamano_maximo": "grande",
            "duracion_maxima_dias": 60,
            "cupo_declarado": 2,
            "acepta_medicacion": True,
            "acepta_conducta": True,
        },
    },
}

BRUNO = {
    "nombre": "Bruno",
    "especie": "perro",
    "tamano": "grande",
    "raza": "mestizo",
    "color": "marrón",
    "requiere_medicacion": True,
}


class Command(BaseCommand):
    help = "Carga los hogares de tránsito de ejemplo, un moderador y a Bruno (perro grande)."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="demo-huella-2026")

    @transaction.atomic
    def handle(self, *args, password, **opciones):
        moderador = self._moderador(password)
        hogares = {clave: self._hogar(datos, password) for clave, datos in HOGARES.items()}
        self._suspender(hogares["valeria"], moderador)
        bruno = self._bruno()
        self._resumen(hogares, bruno, password)

    def _usuario(self, email, nombre_usuario, punto, password, **extra):
        modelo = get_user_model()
        usuario = modelo.objects.filter(email=email).first()
        if usuario is None:
            usuario = modelo.objects.create_user(
                email, nombre_usuario, password, estado_cuenta=EstadoCuenta.ACTIVA, **extra
            )
        guardar_domicilio(usuario, Point(*punto, srid=4326))
        return usuario

    def _moderador(self, password):
        email, nombre_usuario, punto = MODERADOR
        return self._usuario(email, nombre_usuario, punto, password, rol=Rol.MODERADOR)

    def _hogar(self, datos, password):
        usuario = self._usuario(datos["email"], datos["nombre_usuario"], datos["punto"], password)
        Domicilio.objects.filter(usuario=usuario).update(**datos["vivienda"])
        perfil = dict(datos["perfil"])
        pausa_dias = perfil.pop("pausa_dias", None)
        if pausa_dias:
            perfil["disponibilidad"] = False
            perfil["pausa_hasta"] = timezone.localdate() + timedelta(days=pausa_dias)
        else:
            perfil["disponibilidad"] = True
        servicios.guardar_perfil_transito(usuario, **perfil)
        return usuario

    def _suspender(self, usuario, moderador):
        if sancion_vigente(usuario) is None:
            sancionar(usuario, Sancion.Tipo.TEMPORAL, "Cuenta de ejemplo para la demo", moderador)

    def _bruno(self):
        ficha = FichaAnimal.objects.filter(nombre=BRUNO["nombre"]).first()
        return ficha or crear_ficha_sin_responsable(BRUNO)

    def _resumen(self, hogares, bruno, password):
        compatibles = {p.usuario_id for p in servicios.hogares_compatibles(bruno)}
        self.stdout.write("Hogares de ejemplo (aviso por Bruno, perro grande con medicación):")
        for usuario in hogares.values():
            perfil = PerfilTransito.objects.get(usuario=usuario)
            if servicios.hogar_habilitado(perfil):
                motivos = servicios.incompatibilidades(perfil, bruno)
                estado = "se le avisa" if usuario.pk in compatibles else "habilitado, no compatible"
                detalle = f" ({'; '.join(motivos)})" if motivos else ""
            else:
                estado, detalle = "no habilitado", ""
            self.stdout.write(f"  - {usuario.email}: {estado}{detalle}")
        self.stdout.write(
            self.style.SUCCESS(
                f"Listo. Moderador: {MODERADOR[0]}. Contraseña de las cuentas demo: {password}"
            )
        )
