"""Conciliação e dados de mercado."""

from datetime import date
from decimal import Decimal

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    CURRENCY,
    MONEY,
    PRICE,
    QUANTITY,
    RATE,
    Base,
    IdMixin,
    UserOwnedMixin,
)


class PositionSnapshot(IdMixin, UserOwnedMixin, Base):
    """Posição informada por um relatório consolidado. Gabarito, não verdade."""

    __tablename__ = "position_snapshot"
    __table_args__ = (UniqueConstraint("import_file_id", "account_id", "asset_id"),)

    import_file_id: Mapped[int] = mapped_column(ForeignKey("import_file.id"))
    ref_date: Mapped[date]
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"))
    quantity: Mapped[Decimal] = mapped_column(QUANTITY)
    reported_price: Mapped[Decimal | None] = mapped_column(PRICE)
    reported_value: Mapped[Decimal | None] = mapped_column(MONEY)
    reported_cost: Mapped[Decimal | None] = mapped_column(MONEY)


class Price(Base):
    """Cotação de fechamento, gravada pelo job diário."""

    __tablename__ = "price"

    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), primary_key=True)
    price_date: Mapped[date] = mapped_column(primary_key=True)
    close: Mapped[Decimal] = mapped_column(PRICE)
    source: Mapped[str] = mapped_column(String(32))


class FxRate(Base):
    """Taxa de câmbio (PTAX do Banco Central), compra e venda."""

    __tablename__ = "fx_rate"

    currency: Mapped[str] = mapped_column(CURRENCY, primary_key=True)
    rate_date: Mapped[date] = mapped_column(primary_key=True)
    buy: Mapped[Decimal] = mapped_column(RATE)
    sell: Mapped[Decimal] = mapped_column(RATE)
    source: Mapped[str] = mapped_column(String(32))
