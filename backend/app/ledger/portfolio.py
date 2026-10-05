"""Ponte banco → motor: lê os lançamentos e os eventos curados e calcula a carteira.

O banco guarda ids (ativo 42, conta 7); o motor entende códigos ("WEGE3") e o nome
canônico da corretora. Lançamento marcado como duplicata (duplicate_of_id) fica de fora.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.engine.positions import (
    Bonus,
    CuratedEvents,
    Entry,
    PortfolioState,
    Subscription,
    TickerChange,
    compute_portfolio,
)
from app.models import Account, Asset, CorporateEvent, Institution, LedgerEntry, SubscriptionOffer
from app.models.enums import AssetClass, CorporateEventType


def compute_user_portfolio(
    session: Session, user_id: int, until: date | None = None
) -> PortfolioState:
    return compute_portfolio(load_entries(session, user_id), load_curated_events(session), until)


def load_entries(session: Session, user_id: int) -> list[Entry]:
    rows = session.execute(
        select(LedgerEntry, Asset.canonical_code, Institution.name)
        .join(Asset, Asset.id == LedgerEntry.asset_id)
        .join(Account, Account.id == LedgerEntry.account_id)
        .join(Institution, Institution.id == Account.institution_id)
        .where(LedgerEntry.user_id == user_id, LedgerEntry.duplicate_of_id.is_(None))
        .order_by(LedgerEntry.trade_date, LedgerEntry.id)
    )
    return [
        Entry(
            trade_date=e.trade_date,
            entry_type=e.entry_type,
            direction=e.direction,
            asset=code,
            account=institution,
            quantity=e.quantity,
            amount=e.gross_amount,
            tax_withheld=e.tax_withheld,
            affects_position=e.affects_position,
        )
        for e, code, institution in rows
    ]


def load_curated_events(session: Session) -> CuratedEvents:
    """Eventos do catálogo compartilhado (valem para todos os usuários, ADR 0002)."""
    source, target = aliased(Asset), aliased(Asset)
    changes = session.execute(
        select(source.canonical_code, target.canonical_code, CorporateEvent.ex_date)
        .join(source, source.id == CorporateEvent.source_asset_id)
        .join(target, target.id == CorporateEvent.target_asset_id)
        .where(CorporateEvent.event_type == CorporateEventType.TROCA_TICKER)
        .order_by(CorporateEvent.ex_date, CorporateEvent.id)
    )
    # Sem custo informado, a bonificação fica de fora: o motor assume zero e sinaliza.
    bonuses = session.execute(
        select(Asset.canonical_code, CorporateEvent.ex_date, CorporateEvent.cost_per_unit)
        .join(Asset, Asset.id == CorporateEvent.source_asset_id)
        .where(
            CorporateEvent.event_type == CorporateEventType.BONIFICACAO,
            CorporateEvent.cost_per_unit.is_not(None),
        )
        .order_by(CorporateEvent.ex_date, CorporateEvent.id)
    )
    return CuratedEvents(
        ticker_changes=tuple(TickerChange(old, new, day) for old, new, day in changes),
        bonuses=tuple(Bonus(code, day, cost) for code, day, cost in bonuses),
        subscriptions=_subscriptions(session),
    )


def _subscriptions(session: Session) -> tuple[Subscription, ...]:
    """Direito → recibo → ativo. O recibo é o ativo da classe RECIBO_SUBSCRICAO que aponta
    para o mesmo ativo; oferta sem recibo cadastrado (direito expirado) fica de fora."""
    right, underlying, receipt = aliased(Asset), aliased(Asset), aliased(Asset)
    rows = session.execute(
        select(right.canonical_code, receipt.canonical_code, underlying.canonical_code)
        .select_from(SubscriptionOffer)
        .join(right, right.id == SubscriptionOffer.right_asset_id)
        .join(underlying, underlying.id == SubscriptionOffer.underlying_asset_id)
        .join(
            receipt,
            (receipt.underlying_asset_id == underlying.id)
            & (receipt.asset_class == AssetClass.RECIBO_SUBSCRICAO),
        )
        .order_by(SubscriptionOffer.id)
    )
    return tuple(Subscription(r, rec, u) for r, rec, u in rows)
