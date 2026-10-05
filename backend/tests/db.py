"""Banco real dos testes: o Postgres local fingertip_test, nunca outro."""

import os
from pathlib import Path

from alembic.config import Config
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]

# TEST_DATABASE_URL permite trocar (ex.: no CI), mas a trava abaixo vale para qualquer valor.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://localhost/fingertip_test"
)

LOCAL_HOSTS = {None, "", "localhost", "127.0.0.1", "::1"}


def ensure_safe_test_url(url: str) -> None:
    """Recusa banco fora deste computador ou sem o sufixo _test.

    Os testes criam tabelas e apagam o que escrevem: num banco errado, seria um desastre.
    """
    parsed = make_url(url)
    if parsed.host not in LOCAL_HOSTS or not (parsed.database or "").endswith("_test"):
        # render_as_string esconde a senha por padrão.
        raise RuntimeError(
            f"Banco de teste recusado: {parsed.render_as_string()}. "
            "Use um Postgres local com nome terminado em _test."
        )


def alembic_config() -> Config:
    """Config do Alembic apontando para as migrations do backend, de qualquer pasta."""
    config = Config(BACKEND_DIR / "alembic.ini")
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    # Não deixar o Alembic reconfigurar o logging do pytest.
    config.attributes["configure_logger"] = False
    return config
