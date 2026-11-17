"""Carga datos de prueba realistas de Ushuaia: personas, mascotas y publicaciones.

Con --vaciar, antes borra todo menos los superusuarios y la configuración (ver
apps/core/datos_prueba/vaciar.py). Como también se usa en el servidor, pide confirmación;
--sin-preguntar es para los tests.
"""

import logging
from contextlib import contextmanager

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.core.datos_prueba.mascotas import cargar_mascotas
from apps.core.datos_prueba.personas import cargar_personas
from apps.core.datos_prueba.vaciar import vaciar_base

CONFIRMACION = "vaciar"


class Command(BaseCommand):
    help = "Carga datos de prueba de Ushuaia; con --vaciar, antes borra la base."

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True, help="Contraseña de las cuentas de prueba")
        parser.add_argument("--vaciar", action="store_true", help="Borrar todo antes de cargar")
        parser.add_argument("--sin-preguntar", action="store_true", help="No pedir confirmación")

    def handle(self, *args, password, vaciar, sin_preguntar, **opciones):
        if vaciar:
            self._vaciar(sin_preguntar)
        personas = cargar_personas(password)
        self.stdout.write(f"Personas: {len(personas)} cuentas.")
        with self._sin_trazas_de_vision():
            if cargar_mascotas(personas):
                self.stdout.write("Mascotas: fichas, fotos, publicaciones y recorridos cargados.")
            else:
                self.stdout.write("Mascotas: ya estaban cargadas, no se tocaron.")
        self.stdout.write(self.style.SUCCESS("Listo. Probá con lucia.fernandez@example.com."))

    def _vaciar(self, sin_preguntar):
        if not sin_preguntar:
            aviso = "Se va a borrar todo menos los superusuarios."
            respuesta = input(f"{aviso} Escribí «{CONFIRMACION}» para seguir: ")
            if respuesta.strip() != CONFIRMACION:
                raise CommandError("No se borró nada.")
        borrados = vaciar_base()
        detalle = ", ".join(f"{cantidad} {nombre}" for nombre, cantidad in borrados.items())
        self.stdout.write(f"Base vaciada: {detalle}.")

    @contextmanager
    def _sin_trazas_de_vision(self):
        """Sin el modelo de visión, cada foto deja una traza en el log: con un aviso alcanza."""
        registro = logging.getLogger("apps.imagenes.servicios")
        nivel = registro.level
        if not settings.VISION_MODEL_PATH.exists():
            self.stdout.write("No está el modelo de visión: las fotos se guardan sin verificar.")
            registro.setLevel(logging.CRITICAL)
        try:
            yield
        finally:
            registro.setLevel(nivel)
