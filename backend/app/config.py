"""Configuração da aplicação, lida do .env do ambiente (APP_ENV) na raiz do repositório."""

import os
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> parents[2] = raiz do repo
ROOT_DIR = Path(__file__).resolve().parents[2]

# Cada ambiente tem o seu arquivo; nunca misturar (dev local, demo e prod no Neon).
ENV_FILES = {"dev": ".env", "demo": ".env.demo", "prod": ".env.prod"}


def env_file_for(app_env: str) -> Path:
    """Arquivo .env do ambiente pedido; recusa nomes desconhecidos."""
    try:
        return ROOT_DIR / ENV_FILES[app_env]
    except KeyError:
        valid = ", ".join(ENV_FILES)
        raise ValueError(f"APP_ENV inválido: {app_env!r} (use {valid})") from None


class Settings(BaseSettings):
    database_url: str
    # Chave do crachá que o servidor do Next.js assina (ADR 0004). Sem ela, a API recusa
    # todo login; jobs e migrations não precisam dela.
    api_jwt_secret: SecretStr | None = None
    # De onde o navegador pode chamar a API (CORS).
    frontend_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(extra="ignore")

    @property
    def sqlalchemy_url(self) -> str:
        """URL no formato do SQLAlchemy com psycopg 3.

        O Neon entrega postgresql://...; o SQLAlchemy usaria o driver antigo (psycopg2)
        com esse prefixo, então trocamos por postgresql+psycopg://.
        """
        for prefix in ("postgresql://", "postgres://"):
            if self.database_url.startswith(prefix):
                return "postgresql+psycopg://" + self.database_url[len(prefix) :]
        return self.database_url


settings = Settings(_env_file=env_file_for(os.environ.get("APP_ENV", "dev")))
