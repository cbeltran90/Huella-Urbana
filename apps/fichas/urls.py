from django.urls import path

from . import views

app_name = "fichas"

urlpatterns = [
    path("", views.mis_fichas, name="mis_fichas"),
    path("nueva/", views.ficha_nueva, name="nueva"),
    path("<int:pk>/", views.ficha_detalle, name="detalle"),
    path("<int:pk>/editar/", views.ficha_editar, name="editar"),
    path("<int:pk>/baja/", views.ficha_baja, name="baja"),
]
