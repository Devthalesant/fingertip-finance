"""Limite de requisições por usuário (ADR 0004): a "fila furada" não passa."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import rate_limit
from app.api.rate_limit import RateLimiter
from app.models import AppUser
from sample_data.b3_format import write_movement_statement
from sample_data.scenario import movement_rows
from tests.api import bearer, make_token


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_allows_up_to_the_limit_then_refuses() -> None:
    limiter = RateLimiter(Clock())
    assert [limiter.hit("api", 1, 3, 60) for _ in range(3)] == [None, None, None]
    assert limiter.hit("api", 1, 3, 60) == pytest.approx(60)


def test_window_slides() -> None:
    clock = Clock()
    limiter = RateLimiter(clock)
    limiter.hit("api", 1, 2, 60)
    clock.now += 30
    limiter.hit("api", 1, 2, 60)
    assert limiter.hit("api", 1, 2, 60) == pytest.approx(30)  # a 1ª sai da janela em 30 s
    clock.now += 31
    assert limiter.hit("api", 1, 2, 60) is None


def test_refused_requests_do_not_extend_the_wait() -> None:
    # Insistir enquanto bloqueado não empurra a liberação para frente.
    clock = Clock()
    limiter = RateLimiter(clock)
    limiter.hit("api", 1, 1, 60)
    for _ in range(50):
        limiter.hit("api", 1, 1, 60)
    clock.now += 61
    assert limiter.hit("api", 1, 1, 60) is None


def test_each_user_and_bucket_has_its_own_count() -> None:
    limiter = RateLimiter(Clock())
    limiter.hit("api", 1, 1, 60)
    assert limiter.hit("api", 2, 1, 60) is None
    assert limiter.hit("upload", 1, 1, 60) is None
    assert limiter.hit("api", 1, 1, 60) is not None


@pytest.fixture
def owner(db_session: Session) -> AppUser:
    user = AppUser(email="demo@example.com")
    db_session.add(user)
    db_session.flush()
    return user


def test_api_answers_429_with_retry_after(
    client: TestClient, owner: AppUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(rate_limit.LIMITS, "api", (2, 60))
    headers = bearer(make_token())
    assert [client.get("/me", headers=headers).status_code for _ in range(2)] == [200, 200]
    refused = client.get("/me", headers=headers)
    assert refused.status_code == 429
    assert 1 <= int(refused.headers["Retry-After"]) <= 60


@pytest.mark.parametrize("path", ["/me", "/portfolio", "/imports"])
def test_every_data_endpoint_is_limited(
    client: TestClient, owner: AppUser, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    monkeypatch.setitem(rate_limit.LIMITS, "api", (1, 60))
    headers = bearer(make_token())
    client.get(path, headers=headers)
    assert client.get(path, headers=headers).status_code == 429


def test_upload_has_its_own_tighter_limit(
    client: TestClient, owner: AppUser, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(rate_limit.LIMITS, "upload", (1, 3600))
    data = write_movement_statement(movement_rows(), tmp_path / "m.xlsx").read_bytes()
    files = {"file": ("m.xlsx", data, "application/octet-stream")}
    headers = bearer(make_token())
    assert client.post("/imports/b3-movements", files=files, headers=headers).status_code == 200
    assert client.post("/imports/b3-movements", files=files, headers=headers).status_code == 429
    # O limite do upload não trava o resto da API.
    assert client.get("/portfolio", headers=headers).status_code == 200


def test_health_is_not_limited(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(rate_limit.LIMITS, "api", (1, 60))
    assert {client.get("/health").status_code for _ in range(5)} == {200}
