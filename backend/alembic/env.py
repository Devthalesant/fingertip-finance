"""Ambiente do Alembic: de onde vem a URL do banco e quais modelos comparar."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url() -> str:
    # Importado aqui: o modo offline não precisa do .env (roda até no CI).
    from app.config import settings

    return settings.sqlalchemy_url


def run_migrations_offline() -> None:
    """Gera o SQL sem conectar (uv run alembic upgrade head --sql)."""
    context.configure(
        dialect_name="postgresql",
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica as migrations no banco."""
    # NullPool: uma conexão só, fechada no fim. Não faz sentido manter pool num comando.
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
