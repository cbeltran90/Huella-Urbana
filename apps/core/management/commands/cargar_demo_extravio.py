"""Datos de prueba del recorrido 2 de la demo: "extravío con coincidencia".

Deja listas a Nina (con extravío vigente) y a Pipo (ficha privada, sin extravío), cada una con
su responsable, y a Camila, que durante la demo publica el hallazgo de un gato gris mediano.
Se puede correr las veces que haga falta: no duplica nada.
"""

import mimetypes
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cuentas.models import EstadoCuenta
from apps.cuentas.servicios import guardar_domicilio
from apps.fichas.models import FichaAnimal
from apps.fichas.servicios import crear_ficha
from apps.imagenes.models import Fotografia
from apps.imagenes.servicios import registrar_fotografia
from apps.publicaciones import ubicacion
from apps.publicaciones.models import Publicacion

# (correo, nombre de usuario, (longitud, latitud) del domicilio)
PERSONAS = {
    "sofia": ("sofia@demo.huella.test", "sofia_demo", (-68.1950, -54.7990)),  # Playa Larga
    "joaquin": ("joaquin@demo.huella.test", "joaquin_p", (-68.2800, -54.8100)),
    "camila": ("camila@demo.huella.test", "camila_demo", (-68.3000, -54.8050)),
}

NINA = {
    "nombre": "Nina",
    "especie": "gato",
    "tamano": "mediano",
    "raza": "mestizo",
    "color": "gris",
    "castrado": True,
}
PIPO = {
    "nombre": "Pipo",
    "especie": "gato",
    "tamano": "mediano",
    "raza": "mestizo",
    "color": "atigrado",
    "castrado": True,
    "vacunado": True,
}


class Command(BaseCommand):
    help = "Carga los datos del recorrido «extravío con coincidencia» (Nina, Pipo y Camila)."

    def add_arguments(self, parser):
        parser.add_argument("--password", default="demo-huella-2026")
        parser.add_argument("--foto-nina", help="Ruta de una foto de un gato gris para Nina")
        parser.add_argument("--foto-pipo", help="Ruta de una foto de un gato atigrado para Pipo")

    @transaction.atomic
    def handle(self, *args, password, foto_nina=None, foto_pipo=None, **opciones):
        usuarios = {clave: self._usuario(*datos, password) for clave, datos in PERSONAS.items()}
        nina = self._ficha(usuarios["sofia"], NINA)
        pipo = self._ficha(usuarios["joaquin"], PIPO)
        self._foto(foto_nina, usuarios["sofia"], nina)
        self._foto(foto_pipo, usuarios["joaquin"], pipo)
        self._extravio(usuarios["sofia"], nina)
        self.stdout.write(
            self.style.SUCCESS(
                "Listo: Nina (extravío vigente), Pipo (ficha privada) y Camila. "
                f"Contraseña de las cuentas demo: {password}"
            )
        )

    def _usuario(self, email, nombre_usuario, lon_lat, password):
        modelo = get_user_model()
        usuario = modelo.objects.filter(email=email).first()
        if usuario is None:
            usuario = modelo.objects.create_user(
                email, nombre_usuario, password, estado_cuenta=EstadoCuenta.ACTIVA
            )
        guardar_domicilio(usuario, Point(*lon_lat, srid=4326))
        return usuario

    def _ficha(self, responsable, datos):
        ficha = FichaAnimal.objects.filter(nombre=datos["nombre"], responsable=responsable).first()
        return ficha or crear_ficha(responsable, datos)

    def _extravio(self, autor, ficha):
        publicacion = Publicacion.objects.filter(
            tipo=Publicacion.Tipo.EXTRAVIO, ficha=ficha, estado=Publicacion.Estado.VIGENTE
        ).first()
        if publicacion is None:
            Publicacion.objects.create(
                tipo=Publicacion.Tipo.EXTRAVIO,
                autor=autor,
                ficha=ficha,
                ubicacion=ubicacion.punto_de_domicilio(autor),
                descripcion="Se escapó de casa. Es muy cariñosa.",
                especie=ficha.especie,
                tamano=ficha.tamano,
                raza=ficha.raza,
                color=ficha.color,
            )

    def _foto(self, ruta, autor, ficha):
        """Agrega la foto indicada si la ficha todavía no tiene ninguna."""
        if not ruta or Fotografia.objects.filter(ficha=ficha).exists():
            return
        tipo = mimetypes.guess_type(ruta)[0] or "image/jpeg"
        archivo = SimpleUploadedFile(Path(ruta).name, Path(ruta).read_bytes(), content_type=tipo)
        registrar_fotografia(archivo=archivo, autor=autor, ficha=ficha)
