"""Configuração da aplicação, lida do arquivo .env na raiz do repositório."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> parents[2] = raiz do repo
ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str

    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

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


settings = Settings()
