"""Gravador: extrato da B3 → banco, nas três camadas (arquivo → linha bruta → lançamento)."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ledger.importer import import_b3_movements
from app.models import (
    Account,
    AppUser,
    Asset,
    ImportFile,
    Institution,
    InstitutionAlias,
    LedgerEntry,
    RawRow,
)
from app.models.enums import AssetClass, EntryOrigin
from app.models.enums import EntryType as T
from sample_data.b3_format import write_movement_statement
from sample_data.scenario import WEGE3, lend, movement_rows

STORY_ROWS = len(movement_rows())


@pytest.fixture
def user(db_session: Session) -> AppUser:
    user = AppUser(email="demo@example.com")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def story_file(tmp_path: Path) -> Path:
    return write_movement_statement(movement_rows(), tmp_path / "movimentacao.xlsx")


def count(session: Session, model, user: AppUser | None = None) -> int:
    query = select(func.count()).select_from(model)
    if user is not None:
        query = query.where(model.user_id == user.id)
    return session.scalar(query)


def entries(session: Session, user: AppUser) -> list[LedgerEntry]:
    return list(session.scalars(select(LedgerEntry).where(LedgerEntry.user_id == user.id)))


def test_story_lands_in_three_layers(db_session: Session, user: AppUser, story_file: Path) -> None:
    result = import_b3_movements(db_session, user.id, story_file)
    assert not result.already_imported
    assert (result.new_rows, result.skipped_rows, result.ledger_entries) == (
        STORY_ROWS,
        0,
        STORY_ROWS,
    )
    assert count(db_session, ImportFile, user) == 1
    assert count(db_session, RawRow, user) == STORY_ROWS
    saved = entries(db_session, user)
    assert len(saved) == STORY_ROWS
    assert all(e.origin is EntryOrigin.IMPORT and e.parser_version for e in saved)


def test_same_file_twice_changes_nothing(
    db_session: Session, user: AppUser, story_file: Path
) -> None:
    first = import_b3_movements(db_session, user.id, story_file)
    again = import_b3_movements(db_session, user.id, story_file)
    assert again.already_imported
    assert again.import_file_id == first.import_file_id
    assert count(db_session, RawRow, user) == STORY_ROWS
    assert count(db_session, LedgerEntry, user) == STORY_ROWS


def test_overlapping_file_adds_only_new_rows(
    db_session: Session, user: AppUser, tmp_path: Path
) -> None:
    rows = movement_rows()
    # Dois exports que se sobrepõem: o segundo repete as 10 primeiras linhas.
    first = write_movement_statement(rows[:20], tmp_path / "a.xlsx")
    second = write_movement_statement(rows[10:], tmp_path / "b.xlsx")
    import_b3_movements(db_session, user.id, first)
    result = import_b3_movements(db_session, user.id, second)
    assert (result.new_rows, result.skipped_rows) == (STORY_ROWS - 20, 10)
    assert count(db_session, RawRow, user) == STORY_ROWS
    assert count(db_session, LedgerEntry, user) == STORY_ROWS


def test_broker_spellings_become_one_institution_and_one_account(
    db_session: Session, user: AppUser, story_file: Path
) -> None:
    import_b3_movements(db_session, user.id, story_file)
    names = set(db_session.scalars(select(Institution.name)))
    assert names == {"FICTICIA CORRETORA DE VALORES S/A", "EXEMPLAR INVESTIMENTOS CTVM S.A."}
    # Cada grafia que apareceu fica registrada como alias (2 por corretora).
    assert count(db_session, InstitutionAlias) == 4
    assert count(db_session, Account, user) == 2


def test_new_assets_wait_for_classification_and_known_ones_are_reused(
    db_session: Session, user: AppUser, story_file: Path
) -> None:
    db_session.add(Asset(canonical_code="WEGE3", name="WEG S/A", asset_class=AssetClass.ACAO))
    db_session.flush()
    import_b3_movements(db_session, user.id, story_file)
    classes = dict(db_session.execute(select(Asset.canonical_code, Asset.asset_class)).all())
    assert classes["WEGE3"] is AssetClass.ACAO  # já estava no catálogo: reaproveitado
    assert classes["PETR4"] is AssetClass.A_CLASSIFICAR
    assert classes["23C01234567"] is AssetClass.A_CLASSIFICAR
    # Catálogo compartilhado: sem dono, um por código.
    assert db_session.scalar(select(func.count()).where(Asset.owner_user_id.is_not(None))) == 0
    assert db_session.scalar(select(func.count(Asset.canonical_code.distinct()))) == count(
        db_session, Asset
    )


def test_loan_return_points_to_the_loan_out(
    db_session: Session, user: AppUser, story_file: Path
) -> None:
    import_b3_movements(db_session, user.id, story_file)
    by_type = {e.entry_type: e for e in entries(db_session, user)}
    back, out = by_type[T.ALUGUEL_RETORNO], by_type[T.ALUGUEL_SAIDA]
    assert back.related_entry_id == out.id
    assert not back.affects_position


def test_loan_split_across_two_files_is_still_a_loan(
    db_session: Session, user: AppUser, tmp_path: Path
) -> None:
    # A saída vem num export e a devolução no seguinte: o ledger é refeito com tudo.
    rows = lend(
        WEGE3,
        100,
        "CORRETORA ALFA S/A",
        date(2022, 9, 1),
        date(2022, 12, 1),
        "29.00",
        fee=(date(2022, 12, 5), "18.00"),
    )
    before = [r for r in rows if r.date < date(2022, 12, 1)]
    after = [r for r in rows if r.date >= date(2022, 12, 1)]
    import_b3_movements(db_session, user.id, write_movement_statement(after, tmp_path / "b.xlsx"))
    import_b3_movements(db_session, user.id, write_movement_statement(before, tmp_path / "a.xlsx"))
    types = {e.entry_type for e in entries(db_session, user)}
    assert T.ALUGUEL_RETORNO in types and T.COMPRA not in types


def test_jcp_is_saved_gross_with_tax(db_session: Session, user: AppUser, story_file: Path) -> None:
    import_b3_movements(db_session, user.id, story_file)
    (jcp,) = [
        e
        for e in entries(db_session, user)
        if e.entry_type is T.JCP and e.trade_date == date(2022, 3, 10)
    ]
    assert (jcp.gross_amount, jcp.tax_withheld) == (Decimal("100.00"), Decimal("15.00"))


def test_each_user_has_their_own_rows(db_session: Session, user: AppUser, story_file: Path) -> None:
    other = AppUser(email="outra@example.com")
    db_session.add(other)
    db_session.flush()
    import_b3_movements(db_session, user.id, story_file)
    result = import_b3_movements(db_session, other.id, story_file)
    # O mesmo arquivo é novo para outra pessoa.
    assert not result.already_imported
    assert count(db_session, RawRow, other) == STORY_ROWS
    assert count(db_session, LedgerEntry, user) == STORY_ROWS
