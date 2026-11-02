from django.urls import path

from . import views

app_name = "cuentas"

urlpatterns = [
    path("registro/", views.registro, name="registro"),
    path("registro/listo/", views.registro_listo, name="registro_listo"),
    path("confirmar/<str:token>/", views.confirmar, name="confirmar"),
    path("reenviar/", views.reenviar_confirmacion, name="reenviar"),
    path("reenviar/listo/", views.reenvio_listo, name="reenvio_listo"),
]
