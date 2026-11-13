"""Carga todos los datos de prueba de la demo con un solo comando.

Encadena los recorridos que ya existen:

- "cargar_demo_adopcion": los hogares de tránsito (con "cargar_demo_transito", que corre
  primero) y las cinco mascotas del recorrido de tránsito y adopción.
- "cargar_demo_extravio": Nina, Pipo y Camila, del recorrido de extravío con coincidencia.

Se puede correr las veces que haga falta: ninguno de los dos duplica nada.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Carga todos los datos de prueba de la demo (tránsito, adopción y extravío)."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="demo-huella-2026")
        parser.add_argument("--foto-nina", help="Ruta de una foto de un gato gris para Nina")
        parser.add_argument("--foto-pipo", help="Ruta de una foto de un gato atigrado para Pipo")

    def handle(self, *args, password, foto_nina=None, foto_pipo=None, **opciones):
        self.stdout.write("1/2 Tránsito y adopción...")
        call_command("cargar_demo_adopcion", password=password, stdout=self.stdout)
        self.stdout.write("2/2 Extravío con coincidencia...")
        call_command(
            "cargar_demo_extravio",
            password=password,
            foto_nina=foto_nina,
            foto_pipo=foto_pipo,
            stdout=self.stdout,
        )
        self.stdout.write(
            self.style.SUCCESS(f"Datos de la demo cargados. Contraseña de las cuentas: {password}")
        )
