from django.urls import path

from . import views

app_name = "adopcion"

urlpatterns = [
    path("postular/<int:ficha_pk>/", views.postular, name="postular"),
]
