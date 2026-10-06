"""Crachá assinado do frontend → usuário convidado (ADR 0004).

O servidor do Next.js, depois do login no Auth.js, assina um JWT de vida curta. Aqui a
API confere o crachá e acha o convite pelo e-mail. Os erros não dizem o motivo para
fora: quem tenta forjar não aprende nada com a resposta.
"""

from dataclasses import dataclass

import jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AppUser

ISSUER = "fingertip-web"
AUDIENCE = "fingertip-api"
ALGORITHM = "HS256"
MAX_LIFETIME_SECONDS = 300
# Tolerância para relógios levemente diferentes entre Next.js e API.
LEEWAY_SECONDS = 10
MIN_SECRET_BYTES = 32
REQUIRED_CLAIMS = ["iss", "aud", "iat", "exp", "sub", "email", "provider"]


class InvalidToken(Exception):
    """Crachá ausente, malformado, vencido ou com assinatura errada."""


class NotAllowed(Exception):
    """Crachá válido, mas a pessoa não foi convidada ou a identidade não bate."""


@dataclass(frozen=True)
class Identity:
    email: str
    provider: str
    subject: str


def read_token(token: str, secret: str | None) -> Identity:
    if secret is None or len(secret.encode()) < MIN_SECRET_BYTES:
        # Chave ausente ou fraca: recusar todo login é mais seguro que aceitar qualquer um.
        raise InvalidToken("API_JWT_SECRET ausente ou curta demais")
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            audience=AUDIENCE,
            issuer=ISSUER,
            leeway=LEEWAY_SECONDS,
            options={"require": REQUIRED_CLAIMS},
        )
    except jwt.InvalidTokenError as exc:
        raise InvalidToken(str(exc)) from exc
    if claims["exp"] - claims["iat"] > MAX_LIFETIME_SECONDS:
        raise InvalidToken("crachá com vida longa demais")
    fields = (claims["email"], claims["provider"], claims["sub"])
    if not all(isinstance(f, str) and f.strip() for f in fields):
        raise InvalidToken("e-mail, provedor ou sub vazios")
    return Identity(claims["email"].strip().lower(), claims["provider"], claims["sub"])


def resolve_user(session: Session, identity: Identity) -> AppUser:
    """Convite pelo e-mail; no primeiro acesso, grava a identidade do login."""
    user = session.scalar(select(AppUser).where(func.lower(AppUser.email) == identity.email))
    if user is None:
        raise NotAllowed("e-mail não convidado")
    if user.auth_subject is None:
        user.auth_provider, user.auth_subject = identity.provider, identity.subject
        session.flush()
    elif (user.auth_provider, user.auth_subject) != (identity.provider, identity.subject):
        raise NotAllowed("identidade diferente da registrada")
    return user
