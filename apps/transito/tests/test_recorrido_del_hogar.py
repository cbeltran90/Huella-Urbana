"""El recorrido de una persona nueva hasta ser elegida como hogar de tránsito, por pantallas.

Complementa al recorrido de "apps/adopcion/tests/test_recorrido_completo.py", que usa los
servicios y arranca con las cuentas ya creadas: acá se prueban el registro, la confirmación
del correo, el domicilio, los datos del hogar, el perfil de tránsito, la postulación y la
elección, todo por las mismas pantallas que usa la gente.
"""

import re

import pytest
from django.test import Client
from django.urls import reverse

from apps.cuentas.models import Domicilio, EstadoCuenta, Usuario
from apps.fichas.models import FichaAnimal
from apps.notificaciones.models import Notificacion
from apps.transito.models import Postulacion
from apps.transito.servicios import es_hogar_de_transito

CLAVE = "clave-de-prueba-1"
BACKEND_MODELO = "django.contrib.auth.backends.ModelBackend"
CORREO = "lucia@example.com"
CONTACTO = "2901-555555"

pytestmark = pytest.mark.django_db


def entrar(client):
    return client.post(reverse("cuentas:login"), {"username": CORREO, "password": CLAVE})


def hay_sesion(client):
    return "_auth_user_id" in client.session


def test_de_crear_la_cuenta_a_ser_elegida_como_hogar_de_transito(client, mailoutbox):
    ema = Usuario.objects.create_user(
        "ema@example.com", "Ema", CLAVE, estado_cuenta=EstadoCuenta.ACTIVA
    )
    lola = FichaAnimal.objects.create(
        nombre="Lola",
        especie="perro",
        tamano="mediano",
        estado=FichaAnimal.Estado.EN_ADOPCION,
        es_privada=False,
        cuidador=ema,
    )

    # 1. Lucía crea su cuenta: queda pendiente y todavía no puede entrar.
    respuesta = client.post(
        reverse("cuentas:registro"),
        {
            "nombre_usuario": "Lucia",
            "email": CORREO,
            "password1": CLAVE,
            "password2": CLAVE,
            "acepta_condiciones": "on",
        },
    )
    assert respuesta.url == reverse("cuentas:registro_listo")
    lucia = Usuario.objects.get(email=CORREO)
    assert lucia.estado_cuenta == EstadoCuenta.PENDIENTE
    entrar(client)
    assert not hay_sesion(client)

    # 2. Confirma el correo con el enlace que le llegó: la cuenta queda activa.
    token = re.search(r"/cuentas/confirmar/([^/\s]+)/", mailoutbox[0].body).group(1)
    assert client.get(reverse("cuentas:confirmar", args=[token])).status_code == 200
    lucia.refresh_from_db()
    assert lucia.estado_cuenta == EstadoCuenta.ACTIVA

    # 3. Ahora sí entra.
    entrar(client)
    assert hay_sesion(client)

    # 4. Marca su domicilio en el mapa, y 5. completa los datos de su hogar.
    respuesta = client.post(
        reverse("cuentas:domicilio"), {"latitud": "-54.8100", "longitud": "-68.3100"}
    )
    assert respuesta.status_code == 302
    assert Domicilio.objects.filter(usuario=lucia).exists()
    respuesta = client.post(
        reverse("cuentas:datos_hogar"),
        {
            "tipo_vivienda": "casa",
            "tiene_patio": "True",
            "convivientes": "2",
            "hay_ninos": "False",
            "mascotas_propias": "0",
        },
    )
    assert respuesta.status_code == 302

    # 6. Completa su perfil de hogar de tránsito: desde ahora es un hogar.
    assert not es_hogar_de_transito(lucia)
    respuesta = client.post(
        reverse("transito:perfil_transito"),
        {
            "especies": ["perro"],
            "tamano_maximo": "mediano",
            "duracion_maxima_dias": "30",
            "disponibilidad": "True",
            "cupo_declarado": "2",
        },
    )
    assert respuesta.status_code == 302
    assert es_hogar_de_transito(lucia)

    # 7. Se postula para alojar a Lola; Ema recibe el aviso.
    respuesta = client.post(reverse("transito:postular", args=[lola.pk]), {"contacto": CONTACTO})
    assert respuesta.status_code == 302
    postulacion = Postulacion.objects.get(ficha=lola, usuario=lucia)
    assert postulacion.estado == Postulacion.Estado.PENDIENTE
    assert Notificacion.objects.filter(
        usuario=ema, tipo=Notificacion.Tipo.POSTULACION_RECIBIDA
    ).exists()

    # 8. Ema ve a Lucía entre los postulantes, con su contacto, y la elige.
    de_ema = Client()
    de_ema.force_login(ema, backend=BACKEND_MODELO)
    pantalla = de_ema.get(reverse("transito:elegir_hogar", args=[lola.pk])).content.decode()
    assert "Lucia" in pantalla
    assert CONTACTO in pantalla
    respuesta = de_ema.post(
        reverse("transito:elegir_hogar", args=[lola.pk]), {"postulacion": postulacion.pk}
    )
    assert respuesta.status_code == 302
    postulacion.refresh_from_db()
    assert postulacion.estado == Postulacion.Estado.ELEGIDA
    assert Notificacion.objects.filter(
        usuario=lucia, tipo=Notificacion.Tipo.RESULTADO_POSTULACION
    ).exists()
