"""Ajudantes dos testes da API: crachás fabricados (ADR 0004)."""

import os
import time

import jwt

from app.api.auth import AUDIENCE, ISSUER


def make_token(
    email: str = "demo@example.com",
    *,
    sub: str = "google-123",
    provider: str = "google",
    secret: str | None = None,
    lifetime: int = 300,
    age: int = 0,
    **overrides: object,
) -> str:
    # Por padrão, a chave que o conftest sorteou para a API desta rodada.
    secret = secret or os.environ["API_JWT_SECRET"]
    now = int(time.time()) - age
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + lifetime,
        "email": email,
        "provider": provider,
        "sub": sub,
        **overrides,
    }
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, secret, algorithm="HS256")


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
