"""
Entrypoint — Agente Energía Colombia Backend API.

Uso desarrollo:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Uso producción (via Docker):
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
"""
from src.interface.api.main import app  # noqa: F401 — re-exported for uvicorn
