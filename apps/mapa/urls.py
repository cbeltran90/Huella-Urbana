from django.urls import path

from . import views

app_name = "mapa"

urlpatterns = [
    path("", views.mapa, name="mapa"),
    path("datos/", views.datos, name="datos"),
    path("resumen/<int:pk>/", views.resumen, name="resumen"),
]
