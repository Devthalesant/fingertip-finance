"""A trava que impede os testes de rodarem num banco que não seja o local de teste."""

import pytest

from tests.db import ensure_safe_test_url


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://localhost/fingertip_test",
        "postgresql+psycopg://127.0.0.1:5432/fingertip_test",
        "postgresql+psycopg://user:pw@[::1]/outro_test",
        # Sem host: conexão pelo socket local do Postgres.
        "postgresql+psycopg:///fingertip_test",
    ],
)
def test_accepts_local_test_database(url: str) -> None:
    ensure_safe_test_url(url)


@pytest.mark.parametrize(
    "url",
    [
        # Neon (nuvem), mesmo com sufixo _test.
        "postgresql+psycopg://u:p@ep-x.sa-east-1.aws.neon.tech/fingertip_test",
        # Local, mas o banco do dia a dia.
        "postgresql+psycopg://localhost/fingertip_dev",
        "postgresql+psycopg://localhost/fingertip",
        # "test" no meio do nome não basta.
        "postgresql+psycopg://localhost/test_fingertip",
    ],
)
def test_refuses_anything_else(url: str) -> None:
    with pytest.raises(RuntimeError, match="recusado"):
        ensure_safe_test_url(url)


def test_error_message_hides_password() -> None:
    with pytest.raises(RuntimeError) as exc:
        ensure_safe_test_url("postgresql+psycopg://u:segredo@ep-x.neon.tech/fingertip")
    assert "segredo" not in str(exc.value)
