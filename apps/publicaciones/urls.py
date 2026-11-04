from django.urls import path

from . import views

app_name = "publicaciones"

urlpatterns = [
    path("extravio/", views.publicar_extravio, name="publicar_extravio"),
    path("hallazgo/", views.publicar_hallazgo, name="publicar_hallazgo"),
    path("adopcion/", views.alta_adopcion, name="alta_adopcion"),
    path("<int:pk>/", views.detalle, name="detalle"),
]
