"""Conexão da aplicação com o banco (a API usa; jobs e migrations têm a sua)."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

# pool_pre_ping: o Neon derruba conexões paradas; testa antes de usar.
engine = create_engine(settings.sqlalchemy_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
