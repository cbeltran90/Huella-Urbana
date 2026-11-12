from django.urls import path

from . import views, vistas_ingreso

app_name = "transito"

urlpatterns = [
    path("perfil/", views.perfil_transito, name="perfil_transito"),
    path("perfil/desactivar/", views.desactivar_perfil_transito, name="desactivar_perfil"),
    path("postular/<int:ficha_pk>/", views.postular, name="postular"),
    path("solicitar/<int:ficha_pk>/", views.solicitar, name="solicitar"),
    path("elegir/<int:ficha_pk>/", views.elegir, name="elegir_hogar"),
    path("postulaciones/<int:pk>/retirar/", views.retirar, name="retirar_postulacion"),
    path("ingreso/<int:ficha_pk>/", vistas_ingreso.registrar_ingreso, name="registrar_ingreso"),
    path(
        "cancelar-entrega/<int:ficha_pk>/", vistas_ingreso.cancelar_entrega, name="cancelar_entrega"
    ),
]
