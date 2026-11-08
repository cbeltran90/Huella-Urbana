from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from .forms import InicioSesionForm, NuevaContrasenaForm, RecuperarContrasenaForm

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
        "recuperar/",
        auth_views.PasswordResetView.as_view(
            template_name="cuentas/recuperar.html",
            form_class=RecuperarContrasenaForm,
            email_template_name="cuentas/correo_recuperar.txt",
            subject_template_name="cuentas/correo_recuperar_asunto.txt",
            extra_email_context={"dias": settings.PASSWORD_RESET_TIMEOUT // (24 * 60 * 60)},
            success_url=reverse_lazy("cuentas:recuperar_listo"),
        ),
        name="recuperar",
    ),
    path(
        "recuperar/listo/",
        auth_views.PasswordResetDoneView.as_view(template_name="cuentas/recuperar_listo.html"),
        name="recuperar_listo",
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
    path("domicilio/", views.domicilio, name="domicilio"),
    path("hogar/", views.datos_hogar, name="datos_hogar"),
    path("perfil/", views.perfil, name="perfil"),
    path("perfil/adopcion/", views.perfil_adoptante, name="perfil_adoptante"),
    path("perfil/editar/", views.editar_perfil, name="editar_perfil"),
    path("perfil/contrasena/", views.cambiar_contrasena, name="cambiar_contrasena"),
    path("perfil/eliminar/", views.eliminar_cuenta, name="eliminar_cuenta"),
    path("eliminada/", views.cuenta_eliminada, name="cuenta_eliminada"),
    path("perfil/correo/", views.cambiar_correo, name="cambiar_correo"),
    path("perfil/correo/enviado/", views.cambiar_correo_enviado, name="cambiar_correo_enviado"),
    path("correo/confirmar/<str:token>/", views.confirmar_correo, name="confirmar_correo"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
]
