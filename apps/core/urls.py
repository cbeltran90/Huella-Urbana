from django.urls import path

from apps.mapa.views import mapa

from . import views

app_name = "core"

urlpatterns = [
    # La pantalla de inicio es el mapa (CU-19); conserva el nombre para los redirect
    path("", mapa, name="inicio"),
    path("salud/", views.salud, name="salud"),
]
