"""Confere a migration sem banco: gera o SQL (modo offline) e compara com os modelos."""

import io
import re
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.models import Base

BACKEND_DIR = Path(__file__).resolve().parents[1]


def offline_sql(*args: str) -> str:
    buffer = io.StringIO()
    config = Config(BACKEND_DIR / "alembic.ini", stdout=buffer)
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.output_buffer = buffer
    getattr(command, args[0])(config, args[1], sql=True)
    return buffer.getvalue()


def test_upgrade_creates_every_model_table() -> None:
    sql = offline_sql("upgrade", "head")
    created = set(re.findall(r"^CREATE TABLE (\w+)", sql, flags=re.M))
    assert created - {"alembic_version"} == set(Base.metadata.tables)


def test_constraint_names_are_unique() -> None:
    # DROP CONSTRAINT não conta: uma migration posterior pode trocar uma constraint.
    names = re.findall(r"(?<!DROP )CONSTRAINT (\w+)", offline_sql("upgrade", "head"))
    assert len(names) == len(set(names))


def test_every_model_check_is_in_migration() -> None:
    sql = offline_sql("upgrade", "head")
    for table in Base.metadata.tables.values():
        for constraint in table.constraints:
            if constraint.__class__.__name__ == "CheckConstraint":
                assert f"CONSTRAINT {constraint.name} CHECK" in sql, constraint.name


def test_every_model_index_is_in_migration() -> None:
    # Índice declarado no modelo e esquecido na migration só aparece com volume (ADR 0004).
    sql = offline_sql("upgrade", "head")
    created = set(re.findall(r"^CREATE (?:UNIQUE )?INDEX (\w+)", sql, flags=re.M))
    dropped = set(re.findall(r"^DROP INDEX (\w+)", sql, flags=re.M))
    for table in Base.metadata.tables.values():
        for index in table.indexes:
            assert index.name in created - dropped, index.name


def test_foreign_keys_to_ledger_entry_are_indexed() -> None:
    # Apagar um lançamento obriga o Postgres a procurar quem aponta para ele; sem índice,
    # varre a tabela a cada linha apagada (o ledger é refeito a cada importação).
    entry = Base.metadata.tables["ledger_entry"]
    indexed = {tuple(c.name for c in index.columns)[0] for index in entry.indexes}
    pointing = {fk.parent.name for fk in entry.foreign_keys if fk.column.table is entry}
    assert pointing <= indexed


def test_downgrade_drops_every_table() -> None:
    sql = offline_sql("downgrade", "head:base")
    dropped = set(re.findall(r"^DROP TABLE (\w+)", sql, flags=re.M))
    assert dropped == set(Base.metadata.tables)
