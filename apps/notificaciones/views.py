from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def mis_avisos(request):
    """Avisos de quien mira la página. Al abrirla, quedan todos como leídos."""
    avisos = list(request.user.notificaciones.select_related("ficha", "publicacion"))
    request.user.notificaciones.filter(leida=False).update(leida=True)
    return render(request, "notificaciones/mis_avisos.html", {"avisos": avisos})
