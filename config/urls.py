from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuentas/", include("apps.cuentas.urls")),
    path("fichas/", include("apps.fichas.urls")),
    path("", include("apps.core.urls")),
]
