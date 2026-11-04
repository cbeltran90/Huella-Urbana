from django.db import migrations
from django.db.models import Case, Value, When


def derivar_acceso(apps, schema_editor):
    """Deja is_staff e is_superuser de las cuentas existentes de acuerdo con su rol."""
    Usuario = apps.get_model("cuentas", "Usuario")
    Usuario.objects.update(
        is_staff=Case(
            When(rol__in=["moderador", "administrador"], then=Value(True)),
            default=Value(False),
        ),
        is_superuser=Case(
            When(rol="administrador", then=Value(True)),
            default=Value(False),
        ),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("cuentas", "0004_quitar_direccion_domicilio"),
    ]

    operations = [
        migrations.RunPython(derivar_acceso, migrations.RunPython.noop),
    ]