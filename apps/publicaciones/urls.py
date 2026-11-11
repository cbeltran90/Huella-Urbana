from django.urls import path

from . import views

app_name = "publicaciones"

urlpatterns = [
    path("extravio/", views.publicar_extravio, name="publicar_extravio"),
    path("hallazgo/", views.publicar_hallazgo, name="publicar_hallazgo"),
    path("adopcion/", views.alta_adopcion, name="alta_adopcion"),
    path("coincidencias/", views.coincidencias, name="coincidencias"),
    path("perdidos/", views.perdidos, name="perdidos"),
    path("disponibles/", views.disponibles, name="disponibles"),
    path("mias/", views.mis_publicaciones, name="mis_publicaciones"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/candidatas/", views.candidatas, name="candidatas"),
    path("<int:pk>/desvincular/", views.desvincular, name="desvincular"),
    path("caso/<int:pk>/resolver/", views.resolver_caso, name="resolver_caso"),
    path("<int:pk>/es-el-dueno/", views.confirmar_dueno, name="confirmar_dueno"),
    path(
        "coincidencia/<int:pk>/responder/",
        views.responder_coincidencia,
        name="responder_coincidencia",
    ),
]
