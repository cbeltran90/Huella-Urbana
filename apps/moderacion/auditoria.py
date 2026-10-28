from django.contrib.admin.models import CHANGE, LogEntry


def registrar_accion(usuario, objeto, mensaje):
    """Deja constancia de una acción de moderación en el registro de acciones de Django."""
    LogEntry.objects.log_actions(
        user_id=usuario.pk,
        queryset=[objeto],
        action_flag=CHANGE,
        change_message=mensaje,
        single_object=True,
    )
