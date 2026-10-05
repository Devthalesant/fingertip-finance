"""Ponte banco → motor: lançamentos da pessoa e eventos curados, no formato do motor."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.positions import Bonus, Subscription, TickerChange
from app.ledger.importer import import_b3_movements
from app.ledger.portfolio import load_curated_events, load_entries
from app.models import Account, AppUser, Asset, CorporateEvent, LedgerEntry, SubscriptionOffer
from app.models.enums import AssetClass, CorporateEventType, Direction, EntryOrigin, EntryType
from sample_data.b3_format import write_movement_statement
from sample_data.scenario import movement_rows


def make_user(session: Session, email: str) -> AppUser:
    user = AppUser(email=email)
    session.add(user)
    session.flush()
    return user


def make_asset(session: Session, code: str, cls=AssetClass.ACAO, underlying: Asset | None = None):
    asset = Asset(
        canonical_code=code,
        asset_class=cls,
        underlying_asset_id=underlying.id if underlying else None,
    )
    session.add(asset)
    session.flush()
    return asset


@pytest.fixture
def story_file(tmp_path: Path) -> Path:
    return write_movement_statement(movement_rows(), tmp_path / "movimentacao.xlsx")


def test_entries_use_codes_and_canonical_broker_names(
    db_session: Session, story_file: Path
) -> None:
    user = make_user(db_session, "demo@example.com")
    import_b3_movements(db_session, user.id, story_file)
    entries = load_entries(db_session, user.id)
    assert len(entries) == len(movement_rows())
    (jcp,) = [
        e for e in entries if e.entry_type is EntryType.JCP and e.trade_date == date(2022, 3, 10)
    ]
    assert (jcp.asset, jcp.account) == ("BBAS3", "FICTICIA CORRETORA DE VALORES S/A")
    assert (jcp.amount, jcp.tax_withheld) == (Decimal("100.00"), Decimal("15.00"))


def test_only_the_users_own_entries(db_session: Session, story_file: Path) -> None:
    owner = make_user(db_session, "demo@example.com")
    other = make_user(db_session, "outra@example.com")
    import_b3_movements(db_session, owner.id, story_file)
    assert load_entries(db_session, other.id) == []


def test_duplicate_entries_are_left_out(db_session: Session, story_file: Path) -> None:
    user = make_user(db_session, "demo@example.com")
    import_b3_movements(db_session, user.id, story_file)
    imported = db_session.scalars(
        select(LedgerEntry).where(
            LedgerEntry.user_id == user.id,
            LedgerEntry.entry_type == EntryType.COMPRA,
            LedgerEntry.trade_date == date(2023, 2, 6),
        )
    ).one()  # PETR4
    # A mesma compra lançada à mão antes de importar o extrato.
    manual = LedgerEntry(
        user_id=user.id,
        origin=EntryOrigin.MANUAL,
        account_id=imported.account_id,
        asset_id=imported.asset_id,
        trade_date=imported.trade_date,
        entry_type=EntryType.COMPRA,
        direction=Direction.IN,
        quantity=imported.quantity,
        gross_amount=imported.gross_amount,
        affects_position=True,
        duplicate_of_id=imported.id,
    )
    db_session.add(manual)
    db_session.flush()
    petr_buys = [
        e
        for e in load_entries(db_session, user.id)
        if e.asset == "PETR4" and e.entry_type is EntryType.COMPRA
    ]
    assert len(petr_buys) == 1


def test_curated_events_in_the_motor_format(db_session: Session) -> None:
    viia, bhia, itsa = (make_asset(db_session, c) for c in ("VIIA3", "BHIA3", "ITSA4"))
    knri = make_asset(db_session, "KNRI11", AssetClass.FII)
    right = make_asset(db_session, "KNRI12", AssetClass.DIREITO_SUBSCRICAO, underlying=knri)
    make_asset(db_session, "KNRI13", AssetClass.RECIBO_SUBSCRICAO, underlying=knri)
    cvc = make_asset(db_session, "CVCB3")
    cvc_right = make_asset(db_session, "CVCB1", AssetClass.DIREITO_SUBSCRICAO, underlying=cvc)
    db_session.add_all(
        [
            CorporateEvent(
                event_type=CorporateEventType.TROCA_TICKER,
                ex_date=date(2023, 9, 20),
                source_asset_id=viia.id,
                target_asset_id=bhia.id,
                ratio_from=Decimal(1),
                ratio_to=Decimal(1),
            ),
            CorporateEvent(
                event_type=CorporateEventType.BONIFICACAO,
                ex_date=date(2024, 12, 2),
                source_asset_id=itsa.id,
                ratio_from=Decimal(100),
                ratio_to=Decimal(105),
                cost_per_unit=Decimal("13.55518731"),
            ),
            # Bonificação sem custo informado: o motor assume zero e sinaliza.
            CorporateEvent(
                event_type=CorporateEventType.BONIFICACAO,
                ex_date=date(2025, 12, 1),
                source_asset_id=itsa.id,
                ratio_from=Decimal(100),
                ratio_to=Decimal(105),
            ),
            SubscriptionOffer(
                right_asset_id=right.id,
                underlying_asset_id=knri.id,
                price_per_unit=Decimal("162.74"),
            ),
            # Sem recibo cadastrado (o direito expirou): não vira Subscription.
            SubscriptionOffer(
                right_asset_id=cvc_right.id,
                underlying_asset_id=cvc.id,
                price_per_unit=Decimal("19.12"),
            ),
        ]
    )
    db_session.flush()
    events = load_curated_events(db_session)
    assert events.ticker_changes == (TickerChange("VIIA3", "BHIA3", date(2023, 9, 20)),)
    assert events.bonuses == (Bonus("ITSA4", date(2024, 12, 2), Decimal("13.55518731")),)
    assert events.subscriptions == (Subscription("KNRI12", "KNRI13", "KNRI11"),)


def test_accounts_are_not_shared_between_users(db_session: Session, story_file: Path) -> None:
    # Sanidade do ADR 0002: a mesma corretora, uma conta para cada pessoa.
    a = make_user(db_session, "demo@example.com")
    b = make_user(db_session, "outra@example.com")
    import_b3_movements(db_session, a.id, story_file)
    import_b3_movements(db_session, b.id, story_file)
    owners = set(db_session.scalars(select(Account.user_id)))
    assert owners == {a.id, b.id}
