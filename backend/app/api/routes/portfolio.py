"""GET /portfolio: posições com custo, PM e custódia, mais os avisos do motor.

Sem valor de mercado ainda (v0.2). O frontend só formata: tudo já vem calculado.
"""

from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUserDep, SessionDep
from app.ledger.portfolio import compute_user_portfolio
from app.models import Asset
from app.models.enums import AssetClass

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

CENT = Decimal("0.01")


class AssetOut(BaseModel):
    code: str
    name: str | None
    asset_class: AssetClass


class CustodyOut(BaseModel):
    institution: str
    quantity: str


class PositionOut(BaseModel):
    asset: AssetOut
    quantity: str
    total_cost: str
    average_price: str  # ao centavo, como na nota
    custody: list[CustodyOut]


class FlagOut(BaseModel):
    """Premissa ou inconsistência que a tela mostra (ex.: COST_ASSUMED_ZERO)."""

    date: date
    asset: str
    code: str


class PortfolioOut(BaseModel):
    positions: list[PositionOut]
    flags: list[FlagOut]


@router.get("")
def read_portfolio(session: SessionDep, user: CurrentUserDep) -> PortfolioOut:
    state = compute_user_portfolio(session, user.id)
    assets = _assets(session, user.id, list(state.positions))
    return PortfolioOut(
        positions=[
            PositionOut(
                asset=assets[code],
                quantity=_quantity(p.quantity),
                total_cost=_money(p.total_cost),
                average_price=_money(p.average_price),
                custody=[
                    CustodyOut(institution=name, quantity=_quantity(q))
                    for name, q in sorted(state.custody[code].items())
                ],
            )
            for code, p in state.positions.items()
        ],
        flags=[FlagOut(date=f.date, asset=f.asset, code=f.code) for f in state.flags],
    )


def _assets(session: Session, user_id: int, codes: list[str]) -> dict[str, AssetOut]:
    """Nome e classe pelo código: o ativo privado da pessoa primeiro, depois o catálogo.
    Ativo privado de outra pessoa nunca entra (ADR 0002)."""
    rows = session.scalars(
        select(Asset)
        .where(
            Asset.canonical_code.in_(codes),
            or_(Asset.owner_user_id == user_id, Asset.owner_user_id.is_(None)),
        )
        .order_by(Asset.owner_user_id.is_(None))
    )
    found: dict[str, AssetOut] = {}
    for a in rows:
        found.setdefault(
            a.canonical_code,
            AssetOut(code=a.canonical_code, name=a.name, asset_class=a.asset_class),
        )
    return found


def _money(value: Decimal) -> str:
    return str(value.quantize(CENT, ROUND_HALF_EVEN))


def _quantity(value: Decimal) -> str:
    """Sem zeros sobrando e sem notação científica: 150, 0.3, 12.5."""
    return format(value.normalize(), "f")
