"""Dependências compartilhadas pelos endpoints: sessão do banco e usuário logado."""

import logging
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.auth import InvalidToken, NotAllowed, read_token, resolve_user
from app.config import settings
from app.db import SessionLocal
from app.models import AppUser

log = logging.getLogger(__name__)


def get_session() -> Iterator[Session]:
    """Uma sessão por requisição: commit se deu tudo certo, desfaz se deu erro."""
    with SessionLocal() as session, session.begin():
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

# auto_error=False: a resposta de "sem crachá" é a mesma de "crachá inválido".
_bearer = HTTPBearer(auto_error=False)

UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Não autenticado",
    headers={"WWW-Authenticate": "Bearer"},
)
FORBIDDEN = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso não permitido")


def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AppUser:
    if credentials is None:
        raise UNAUTHORIZED
    secret = settings.api_jwt_secret
    try:
        identity = read_token(
            credentials.credentials, secret.get_secret_value() if secret else None
        )
        return resolve_user(session, identity)
    except InvalidToken as exc:
        # O motivo fica só no log (sem o crachá, que é uma credencial).
        log.info("crachá recusado: %s", exc)
        raise UNAUTHORIZED from None
    except NotAllowed as exc:
        log.info("acesso recusado: %s", exc)
        raise FORBIDDEN from None


CurrentUserDep = Annotated[AppUser, Depends(get_current_user)]
