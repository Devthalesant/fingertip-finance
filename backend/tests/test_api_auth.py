"""Porta da API: crachá assinado do frontend e convite do beta fechado (ADR 0004)."""

from collections.abc import Iterator

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.auth import InvalidToken, read_token
from app.api.deps import get_session
from app.api.main import app
from app.models import AppUser
from tests.api import bearer, make_token


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def invited(db_session: Session) -> AppUser:
    user = AppUser(email="demo@example.com", display_name="Demo")
    db_session.add(user)
    db_session.flush()
    return user


def test_health_needs_no_login() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_me_with_valid_token(client: TestClient, invited: AppUser) -> None:
    response = client.get("/me", headers=bearer(make_token()))
    assert response.status_code == 200
    assert response.json() == {
        "email": "demo@example.com",
        "display_name": "Demo",
        "is_admin": False,
    }


def test_first_access_records_the_login_identity(
    client: TestClient, invited: AppUser, db_session: Session
) -> None:
    client.get("/me", headers=bearer(make_token(sub="google-123")))
    db_session.refresh(invited)
    assert (invited.auth_provider, invited.auth_subject) == ("google", "google-123")


def test_email_is_case_insensitive(client: TestClient, invited: AppUser) -> None:
    response = client.get("/me", headers=bearer(make_token("Demo@Example.COM")))
    assert response.status_code == 200


def test_other_identity_with_same_email_is_refused(client: TestClient, invited: AppUser) -> None:
    # Alguém que assumiu o mesmo e-mail em outro provedor não herda a conta.
    assert client.get("/me", headers=bearer(make_token(sub="google-123"))).status_code == 200
    other = make_token(sub="github-999", provider="github")
    assert client.get("/me", headers=bearer(other)).status_code == 403


def test_not_invited_is_forbidden(client: TestClient, invited: AppUser) -> None:
    response = client.get("/me", headers=bearer(make_token("intruso@example.com")))
    assert response.status_code == 403


def test_missing_token_is_unauthorized(client: TestClient) -> None:
    response = client.get("/me")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(make_token(secret="outra-chave-com-pelo-menos-32-bytes!!"), id="assinatura"),
        pytest.param(make_token(age=400), id="vencido"),
        pytest.param(make_token(lifetime=3600), id="vida-longa-demais"),
        pytest.param(make_token(aud="outra-api"), id="destinatario"),
        pytest.param(make_token(iss="outro-site"), id="emissor"),
        pytest.param(make_token(email=None), id="sem-email"),
        pytest.param(make_token(sub=None), id="sem-sub"),
        pytest.param(make_token(exp=None), id="sem-validade"),
        pytest.param(
            jwt.encode({"email": "demo@example.com"}, None, algorithm="none"), id="alg-none"
        ),
        pytest.param("nao-e-um-jwt", id="lixo"),
    ],
)
def test_bad_tokens_are_unauthorized_with_the_same_answer(
    client: TestClient, invited: AppUser, token: str
) -> None:
    response = client.get("/me", headers=bearer(token))
    assert response.status_code == 401
    # Sem dizer o motivo: quem tenta forjar não aprende nada com a resposta.
    assert response.json() == {"detail": "Não autenticado"}


def test_users_only_see_themselves(
    client: TestClient, invited: AppUser, db_session: Session
) -> None:
    db_session.add(AppUser(email="outra@example.com"))
    db_session.flush()
    response = client.get("/me", headers=bearer(make_token("outra@example.com", sub="g-2")))
    assert response.json()["email"] == "outra@example.com"


@pytest.mark.parametrize("secret", [None, "curta"])
def test_missing_or_weak_secret_refuses_every_token(secret: str | None) -> None:
    # Esquecer a chave no servidor não pode virar "qualquer crachá entra".
    with pytest.raises(InvalidToken):
        read_token(make_token(secret=secret or "x" * 40), secret)


def test_invite_saved_with_capitals_still_matches(client: TestClient, db_session: Session) -> None:
    db_session.add(AppUser(email="Convite@Example.com"))
    db_session.flush()
    response = client.get("/me", headers=bearer(make_token("convite@example.com")))
    assert response.status_code == 200
