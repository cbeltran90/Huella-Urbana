from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Notificacion


@login_required
def mis_avisos(request):
    """Centro de avisos de quien mira la página (CU-50). Verlos no los marca como leídos."""
    avisos = request.user.notificaciones.select_related("ficha", "publicacion")
    presentes = set(avisos.order_by().values_list("tipo", flat=True).distinct())
    tipos = [(valor, nombre) for valor, nombre in Notificacion.Tipo.choices if valor in presentes]
    tipo = request.GET.get("tipo", "")
    if tipo in presentes:
        avisos = avisos.filter(tipo=tipo)
    contexto = {"avisos": avisos, "tipos": tipos, "tipo": tipo}
    return render(request, "notificaciones/mis_avisos.html", contexto)


@login_required
@require_POST
def abrir(request, pk):
    """Marca el aviso como leído y lleva a su publicación o ficha (CU-50, paso 5)."""
    aviso = get_object_or_404(request.user.notificaciones, pk=pk)
    if not aviso.leida:
        aviso.leida = True
        aviso.save(update_fields=["leida"])
    if aviso.publicacion_id:
        return redirect("publicaciones:detalle", pk=aviso.publicacion_id)
    if aviso.ficha_id:
        return redirect("fichas:detalle", pk=aviso.ficha_id)
    return redirect("notificaciones:mis_avisos")
