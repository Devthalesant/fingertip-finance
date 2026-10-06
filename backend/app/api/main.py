"""A API do Fingertip Finance. Rodar: `uv run uvicorn app.api.main:app --reload`."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.limits import BodySizeLimit
from app.api.routes import health, imports, me, portfolio
from app.config import settings

app = FastAPI(title="Fingertip Finance API", version="0.1.0")

# Só o frontend pode chamar a API pelo navegador (ADR 0004).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
# Corta requisição grande enquanto chega, antes de o FastAPI ler o corpo.
app.add_middleware(BodySizeLimit)

app.include_router(health.router)
app.include_router(me.router)
app.include_router(portfolio.router)
app.include_router(imports.router)
