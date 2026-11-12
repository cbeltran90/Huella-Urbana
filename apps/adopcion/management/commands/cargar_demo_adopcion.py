"""Datos de prueba del recorrido de tránsito y adopción.

Deja cinco mascotas que encontró Ema, cada una frenada en un paso distinto del recorrido, para
mostrar cada paso en la demo sin rehacer los anteriores:

- Lola: sin responsable (Ema pide un hogar de tránsito).
- Toto: en adopción, con Lucía y Romina postuladas (Ema elige el hogar).
- Nube: con Romina elegida (Ema o Romina marcan el ingreso).
- Rocco: en tránsito en lo de Lucía, con Ana y Carla postuladas (Lucía elige quién lo adopta).
- Mora: en tránsito en lo de Lucía, con Ana elegida (Lucía concreta la adopción).

Usa los hogares de "cargar_demo_transito", que corre primero. Cada paso pasa por los servicios
reales. Se puede correr las veces que haga falta: si una mascota ya existe, no la toca.
"""

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.adopcion import eleccion, postulaciones
from apps.cuentas.models import Domicilio, EstadoCuenta
from apps.cuentas.servicios import guardar_domicilio, guardar_perfil_adoptante
from apps.fichas.models import FichaAnimal
from apps.fichas.servicios import crear_ficha_sin_responsable
from apps.transito import eleccion as eleccion_transito
from apps.transito import ingreso, solicitud
from apps.transito import postulaciones as postulaciones_transito

PERSONAS = {
    "ema": ("ema@demo.huella.test", "ema_demo", (-68.3040, -54.8025)),  # las encuentra
    "ana": ("ana@demo.huella.test", "ana_demo", (-68.3100, -54.8060)),
    "carla": ("carla@demo.huella.test", "carla_demo", (-68.2800, -54.8050)),
}
VIVIENDA = {
    "tipo_vivienda": "casa",
    "tiene_patio": True,
    "convivientes": 2,
    "hay_ninos": False,
    "mascotas_propias": 0,
}
EXPERIENCIA = {
    "ana": "Tuve perros toda la vida.",
    "carla": "Tengo un gato y quiero sumar un perro.",
}

# Hasta qué paso del recorrido llega cada mascota.
SIN_RESPONSABLE, EN_ADOPCION, HOGAR_ELEGIDO, EN_TRANSITO, ADOPTANTE_ELEGIDO = range(5)

MASCOTAS = [
    (
        {"nombre": "Lola", "especie": "perro", "tamano": "mediano", "color": "negro"},
        SIN_RESPONSABLE,
    ),
    ({"nombre": "Toto", "especie": "perro", "tamano": "grande", "color": "marrón"}, EN_ADOPCION),
    ({"nombre": "Nube", "especie": "perro", "tamano": "pequeno", "color": "blanco"}, HOGAR_ELEGIDO),
    (
        {"nombre": "Rocco", "especie": "perro", "tamano": "mediano", "color": "atigrado"},
        EN_TRANSITO,
    ),
    (
        {"nombre": "Mora", "especie": "perro", "tamano": "mediano", "color": "gris"},
        ADOPTANTE_ELEGIDO,
    ),
]

PROXIMO_PASO = {
    SIN_RESPONSABLE: "Ema pide un hogar de tránsito",
    EN_ADOPCION: "Ema elige el hogar",
    HOGAR_ELEGIDO: "Ema o Romina marcan el ingreso",
    EN_TRANSITO: "Lucía elige quién lo adopta",
    ADOPTANTE_ELEGIDO: "Lucía concreta la adopción",
}


class Command(BaseCommand):
    help = (
        "Carga cinco mascotas, cada una en un paso distinto del recorrido de tránsito y adopción."
    )

    def add_arguments(self, parser):
        parser.add_argument("--password", default="demo-huella-2026")

    @transaction.atomic
    def handle(self, *args, password, **opciones):
        call_command("cargar_demo_transito", password=password, stdout=self.stdout)
        gente = {clave: self._persona(*datos, password) for clave, datos in PERSONAS.items()}
        for clave, experiencia in EXPERIENCIA.items():
            guardar_perfil_adoptante(gente[clave], experiencia)
        modelo = get_user_model()
        gente["lucia"] = modelo.objects.get(email="lucia@demo.huella.test")
        gente["romina"] = modelo.objects.get(email="romina@demo.huella.test")

        self.stdout.write("Recorrido de tránsito y adopción:")
        for datos, paso in MASCOTAS:
            if not FichaAnimal.objects.filter(nombre=datos["nombre"]).exists():
                self._recorrer(datos, paso, gente)
            self.stdout.write(f"  - {datos['nombre']}: {PROXIMO_PASO[paso]}")
        self.stdout.write(self.style.SUCCESS(f"Listo. Contraseña de las cuentas demo: {password}"))

    def _persona(self, email, nombre_usuario, punto, password):
        modelo = get_user_model()
        usuario = modelo.objects.filter(email=email).first()
        if usuario is None:
            usuario = modelo.objects.create_user(
                email, nombre_usuario, password, estado_cuenta=EstadoCuenta.ACTIVA
            )
        guardar_domicilio(usuario, Point(*punto, srid=4326))
        Domicilio.objects.filter(usuario=usuario).update(**VIVIENDA)
        return usuario

    def _recorrer(self, datos, paso, gente):
        """Crea la mascota y la lleva hasta "paso" con los servicios reales."""
        ema, lucia, romina = gente["ema"], gente["lucia"], gente["romina"]
        ficha = crear_ficha_sin_responsable(datos, cuidador=ema)
        if paso == SIN_RESPONSABLE:
            return
        solicitud.solicitar_transito(ficha, ema)
        if paso == EN_ADOPCION:
            for hogar in (lucia, romina):
                postulaciones_transito.postular_transito(hogar, ficha, "2901 555555")
            return
        hogar = romina if paso == HOGAR_ELEGIDO else lucia
        elegida = postulaciones_transito.postular_transito(hogar, ficha, "2901 555555")
        eleccion_transito.elegir_hogar(ficha, ema, elegida)
        if paso == HOGAR_ELEGIDO:
            return
        ingreso.registrar_ingreso(ficha, ema, vacunado=True)
        de_ana = postulaciones.postular_adopcion(gente["ana"], ficha, "ana por whatsapp")
        postulaciones.postular_adopcion(gente["carla"], ficha, "carla por mail")
        if paso == ADOPTANTE_ELEGIDO:
            eleccion.elegir_adoptante(de_ana, lucia)
