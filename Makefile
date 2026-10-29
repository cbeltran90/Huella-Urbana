.PHONY: up down logs shell migrate makemigrations test lint css watch

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f web

shell:
	docker compose exec web python manage.py shell

migrate:
	docker compose exec web python manage.py migrate

makemigrations:
	docker compose exec web python manage.py makemigrations

test:
	docker compose exec web pytest

lint:
	docker compose exec web ruff check .
	docker compose exec web ruff format --check .
	docker compose exec web djlint templates apps --check

css:
	./bin/tailwindcss -i static/src/input.css -o static/css/app.css --minify

watch:
	./bin/tailwindcss -i static/src/input.css -o static/css/app.css --watch
