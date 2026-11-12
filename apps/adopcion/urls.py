from django.urls import path

from . import views

app_name = "adopcion"

urlpatterns = [
    path("postular/<int:ficha_pk>/", views.postular, name="postular"),
    path("postulantes/<int:ficha_pk>/", views.postulantes, name="postulantes"),
    path("elegir/<int:postulacion_pk>/", views.elegir, name="elegir"),
    path("concretar/<int:ficha_pk>/", views.concretar, name="concretar"),
    path("cancelar/<int:ficha_pk>/", views.cancelar, name="cancelar"),
]
