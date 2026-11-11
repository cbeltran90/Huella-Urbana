from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuentas/", include("apps.cuentas.urls")),
    path("fichas/", include("apps.fichas.urls")),
    path("publicaciones/", include("apps.publicaciones.urls")),
    path("", include("apps.core.urls")),
    path("transito/", include("apps.transito.urls")),
    path("adopcion/", include("apps.adopcion.urls")),
    path("avisos/", include("apps.notificaciones.urls")),
    path("mapa/", include("apps.mapa.urls")),
]
