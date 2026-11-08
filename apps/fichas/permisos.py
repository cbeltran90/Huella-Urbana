"""Quién puede ver, editar y dar de baja una ficha."""

from apps.cuentas.models import Rol

from .models import FichaAnimal


def es_moderador(usuario):
    return usuario.is_authenticated and usuario.rol in (Rol.MODERADOR, Rol.ADMINISTRADOR)


def es_responsable(usuario, ficha):
    return usuario.is_authenticated and ficha.responsable_id == usuario.pk


def es_cuidador(usuario, ficha):
    return usuario.is_authenticated and ficha.cuidador_id == usuario.pk


def tiene_adopcion_registrada(ficha):
    """Un animal adoptado es una ficha en "registrado" con un registro Adopcion.

    La regla es del módulo de adopciones (apps/adopcion/servicios.py).
    """
    from apps.adopcion.servicios import tiene_adopcion_registrada as consulta

    return consulta(ficha)


def puede_ver(usuario, ficha):
    """Una ficha privada la ven su responsable, quien la tiene a cargo y los moderadores."""
    if not ficha.es_privada:
        return True
    return es_responsable(usuario, ficha) or es_cuidador(usuario, ficha) or es_moderador(usuario)


def puede_editar(usuario, ficha):
    """El responsable, quien la tiene a cargo o un moderador."""
    return es_responsable(usuario, ficha) or es_cuidador(usuario, ficha) or es_moderador(usuario)


def puede_dar_de_baja(usuario, ficha):
    """Solo el responsable, con la ficha en registrado y sin adopción."""
    return (
        es_responsable(usuario, ficha)
        and ficha.estado == FichaAnimal.Estado.REGISTRADO
        and not tiene_adopcion_registrada(ficha)
    )
