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