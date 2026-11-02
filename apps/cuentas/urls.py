from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import InicioSesionForm

app_name = "cuentas"

urlpatterns = [
    path("registro/", views.registro, name="registro"),
    path("registro/listo/", views.registro_listo, name="registro_listo"),
    path("confirmar/<str:token>/", views.confirmar, name="confirmar"),
    path("reenviar/", views.reenviar_confirmacion, name="reenviar"),
    path("reenviar/listo/", views.reenvio_listo, name="reenvio_listo"),
    path(
        "ingresar/",
        auth_views.LoginView.as_view(
            template_name="cuentas/login.html",
            authentication_form=InicioSesionForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
]
