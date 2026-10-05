"""A fixture db_session: schema real (Alembic) e tudo desfeito ao fim de cada teste."""

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import AppUser
from tests.db import alembic_config


def _count_users(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(AppUser))


# Os dois testes fazem o mesmo de propósito: qualquer que rode depois só começa vazio
# se o anterior foi desfeito.
@pytest.mark.parametrize("email", ["ana@example.com", "bia@example.com"])
def test_each_test_starts_empty_and_sees_its_writes(db_session: Session, email: str) -> None:
    assert _count_users(db_session) == 0
    db_session.add(AppUser(email=email))
    db_session.commit()  # mesmo um commit do código testado é desfeito no fim
    assert _count_users(db_session) == 1


def test_schema_is_at_latest_migration(db_session: Session) -> None:
    current = db_session.execute(text("select version_num from alembic_version")).scalar()
    assert current == ScriptDirectory.from_config(alembic_config()).get_current_head()
