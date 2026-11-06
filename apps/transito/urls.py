from django.urls import path

from . import views

app_name = "transito"

urlpatterns = [
    path("perfil/", views.perfil_transito, name="perfil_transito"),
    path("perfil/desactivar/", views.desactivar_perfil_transito, name="desactivar_perfil"),
]
