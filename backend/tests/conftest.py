import os
from collections.abc import Iterator

import pytest
from alembic import command
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from tests.db import TEST_DATABASE_URL, alembic_config, ensure_safe_test_url

# Os testes nunca usam o banco do .env: uma URL falsa tem prioridade sobre ele.
# Quem precisa de banco de verdade pede a fixture db_session (Postgres local de teste).
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost/test"


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    """Banco de teste zerado e no schema atual, uma vez por rodada do pytest."""
    ensure_safe_test_url(TEST_DATABASE_URL)
    engine = create_engine(TEST_DATABASE_URL)
    try:
        with engine.begin() as connection:
            # Recria do zero: o schema vem só das migrations, sem sobras de rodadas antigas.
            connection.execute(text("drop schema public cascade"))
            connection.execute(text("create schema public"))
            config = alembic_config()
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
    except OperationalError:
        engine.dispose()
        pytest.skip(
            "Postgres local indisponível: confira com pg_isready "
            "(ligar: brew services start postgresql@18; criar: createdb fingertip_test)"
        )
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Sessão num banco real; tudo o que o teste gravar é desfeito no fim, até commits."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        # Commits do código testado viram savepoints dentro da transação de fora.
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()
