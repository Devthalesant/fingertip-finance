import pytest

from app.config import ROOT_DIR, Settings, env_file_for


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "postgresql://u:p@host/db?sslmode=require",
            "postgresql+psycopg://u:p@host/db?sslmode=require",
        ),
        ("postgres://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
    ],
)
def test_sqlalchemy_url_uses_psycopg3(raw: str, expected: str) -> None:
    assert Settings(database_url=raw).sqlalchemy_url == expected


@pytest.mark.parametrize(
    ("app_env", "filename"),
    [("dev", ".env"), ("demo", ".env.demo"), ("prod", ".env.prod")],
)
def test_env_file_follows_app_env(app_env: str, filename: str) -> None:
    assert env_file_for(app_env) == ROOT_DIR / filename


def test_unknown_app_env_is_rejected() -> None:
    with pytest.raises(ValueError, match="APP_ENV"):
        env_file_for("producao")
