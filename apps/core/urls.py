from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("salud/", views.salud, name="salud"),
    path("prueba/", views.prueba, name="prueba"),
    path("prueba/saludo/", views.prueba_saludo, name="prueba_saludo"),
]
