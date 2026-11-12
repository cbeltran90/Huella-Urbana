from django.urls import path

from . import views

app_name = "adopcion"

urlpatterns = [
    path("postular/<int:ficha_pk>/", views.postular, name="postular"),
    path("postulantes/<int:ficha_pk>/", views.postulantes, name="postulantes"),
    path("elegir/<int:postulacion_pk>/", views.elegir, name="elegir"),
]
