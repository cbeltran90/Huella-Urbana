from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import InicioSesionForm, NuevaContrasenaForm

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
    path(
        "recuperar/completo/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="cuentas/recuperar_completo.html"
        ),
        name="recuperar_completo",
    ),
    path(
        "recuperar/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="cuentas/recuperar_confirmar.html",
            form_class=NuevaContrasenaForm,
            success_url=reverse_lazy("cuentas:recuperar_completo"),
        ),
        name="recuperar_confirmar",
    ),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
]
