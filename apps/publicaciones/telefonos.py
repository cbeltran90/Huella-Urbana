import re

# Característica de Ushuaia: la que falta en los números locales de 6 cifras.
CARACTERISTICA_LOCAL = "2901"


def enlace_whatsapp(telefono):
    """El enlace a WhatsApp del teléfono, o "" si no queda un número argentino de 10 cifras."""
    numero = re.sub(r"\D", "", telefono)
    if numero.startswith("54") and len(numero) in (12, 13):
        numero = numero[2:]
        if len(numero) == 11 and numero.startswith("9"):
            numero = numero[1:]
    elif numero.startswith("0"):
        numero = numero[1:]
    # El 15 de los celulares: después de la característica o al principio del número local.
    if len(numero) == 12 and numero[4:6] == "15":
        numero = numero[:4] + numero[6:]
    if len(numero) == 8 and numero.startswith("15"):
        numero = numero[2:]
    if len(numero) == 6:
        numero = CARACTERISTICA_LOCAL + numero
    if len(numero) != 10:
        return ""
    return f"https://wa.me/549{numero}"
