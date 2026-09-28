# Deploy

## Neon

Crear PostgreSQL en Neon y obtener la connection string. Para SQLAlchemy + psycopg usar una URL con este esquema:

```text
postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require
```

## Render

Variables mínimas:

```text
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<secret largo>
DATABASE_URL=<url Neon adaptada a postgresql+psycopg://>
CORS_ORIGINS=https://tu-frontend.example
```

Build command:

```bash
pip install . && alembic upgrade head
```

Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## GitHub Actions / CI

Recomendado para una siguiente iteración:

```text
ruff check
pytest
alembic check
```

Los tests de integración requieren PostgreSQL de CI.
