# Huella Urbana


Plataforma comunitaria geolocalizada. Stack: Django 5.2 LTS + PostGIS + HTMX + Alpine.js + Leaflet.


## Arranque rápido (desarrollo)


```bash
cp .env.example .env
docker compose up --build
```


La app queda en http://localhost:8080


## Flujo de trabajo


- `main` está protegida: no se pushea directo.
- Una rama por tarea: `feat/<tema>`, `fix/<tema>`, `chore/<tema>`.
- Pull Request chico, con al menos una aprobación de otra persona.
- Commits en formato Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`).
- Antes de pushear: `pre-commit run --all-files`.

## Datos de demostración

Para cargar todas las cuentas y los recorridos de la demo (hogares de tránsito, adopción y extravío):

    docker compose exec web python manage.py cargar_demo

Se puede correr las veces que haga falta sin duplicar datos. La contraseña de todas las cuentas demo es `demo-huella-2026` (se cambia con `--password`) y se entra con el correo, por ejemplo `moderador@demo.huella.test`. Para Nina y Pipo se pueden pasar fotos propias con `--foto-nina` y `--foto-pipo`.
