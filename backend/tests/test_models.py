"""Regras do schema que valem para todos os modelos."""

from app.models import Base

# ADR 0002: dados de cada usuário. O resto é catálogo compartilhado.
USER_OWNED = {"account", "import_file", "raw_row", "ledger_entry", "position_snapshot"}


def test_only_user_owned_tables_have_user_id() -> None:
    with_user_id = {name for name, table in Base.metadata.tables.items() if "user_id" in table.c}
    assert with_user_id == USER_OWNED


def test_user_id_is_required_and_indexed() -> None:
    for name in USER_OWNED:
        column = Base.metadata.tables[name].c.user_id
        assert not column.nullable, name
        assert column.index, name
