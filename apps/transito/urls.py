from django.urls import path

from . import views

app_name = "transito"

urlpatterns = [
    path("perfil/", views.perfil_transito, name="perfil_transito"),
    path("perfil/desactivar/", views.desactivar_perfil_transito, name="desactivar_perfil"),
    path("postular/<int:ficha_pk>/", views.postular, name="postular"),
    path("solicitar/<int:ficha_pk>/", views.solicitar, name="solicitar"),
    path("postulaciones/<int:pk>/retirar/", views.retirar, name="retirar_postulacion"),
]
