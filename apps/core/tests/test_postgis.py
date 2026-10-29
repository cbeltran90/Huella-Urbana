import pytest
from django.db import connection


@pytest.mark.django_db
def test_postgis_esta_activo():
    with connection.cursor() as cursor:
        cursor.execute("SELECT PostGIS_Version()")
        assert cursor.fetchone()[0].startswith("3.")


@pytest.mark.django_db
def test_distancia_geografica_en_metros():
    """Dos puntos de Buenos Aires separados por unas decenas de metros."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT ST_Distance(
                ST_SetSRID(ST_MakePoint(-58.3816, -34.6037), 4326)::geography,
                ST_SetSRID(ST_MakePoint(-58.3820, -34.6040), 4326)::geography
            )
            """
        )
        metros = cursor.fetchone()[0]
    assert 0 < metros < 100
