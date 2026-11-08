from django.urls import path

from . import views

app_name = "notificaciones"

urlpatterns = [
    path("", views.mis_avisos, name="mis_avisos"),
]
