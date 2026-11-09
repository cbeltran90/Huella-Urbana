from django.urls import path

from . import views

app_name = "mapa"

urlpatterns = [
    path("datos/", views.datos, name="datos"),
]
