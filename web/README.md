# Fulbacho Django Web

Frontend server-rendered de Fulbacho.

No contiene modelos del dominio. Todas las operaciones de grupos, jugadores, partidos, goles y estadísticas se realizan a través de `fulbacho/api_client` contra FastAPI.

## Local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

Por defecto espera FastAPI en `http://127.0.0.1:8001/api/v1`.
