from .models import Notificacion


def notificar(usuario, tipo, titulo, mensaje="", *, ficha=None, publicacion=None):
    """Crea una notificación para un usuario y la devuelve.

    El push lo envía después el cron.
    Lanza ValueError si 'tipo' no es un valor válido de Notificacion.Tipo.

    'usuario' es el destinatario de la notificación.
    'tipo' es uno de los valores de Notificacion.Tipo.
    'ficha' es opcional y puede ser None o una instancia de FichaAnimal.
    'publicacion' es opcional y puede ser None o una instancia de Publicacion.
    """

    if tipo not in Notificacion.Tipo.values:
        raise ValueError(f"Tipo de notificación inválido: {tipo!r}")

    # TODO: cuando B4 cree Publicacion, agregar la FK al modelo
    # borrar esta guarda y pasar publicacion al crear.
    if publicacion is not None:
        raise NotImplementedError("Notificaciones de publicaciones aún no implementadas")

    return Notificacion.objects.create(
        usuario=usuario,
        tipo=tipo,
        titulo=titulo,
        mensaje=mensaje,
        ficha=ficha,
    )
