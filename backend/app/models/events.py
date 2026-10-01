"""Eventos curados à mão: o que a B3 não explica direito."""

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import PRICE, QUANTITY, Base, IdMixin, enum_column
from app.models.enums import CorporateEventType


class CorporateEvent(IdMixin, Base):
    """Desdobro, grupamento, bonificação, troca de ticker, cisão, incorporação."""

    __tablename__ = "corporate_event"
    __table_args__ = (
        CheckConstraint("ratio_from > 0 AND (ratio_to IS NULL OR ratio_to > 0)", "ratio_positive"),
        CheckConstraint(
            "cost_allocation_pct IS NULL OR cost_allocation_pct BETWEEN 0 AND 100",
            "cost_allocation_range",
        ),
    )

    event_type: Mapped[CorporateEventType] = mapped_column(enum_column(CorporateEventType))
    ex_date: Mapped[date]
    source_asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"))
    # Ativo resultante (troca de ticker, cisão, incorporação).
    target_asset_id: Mapped[int | None] = mapped_column(ForeignKey("asset.id"))
    # Proporção: 1 para 10 no desdobro = ratio_from 1, ratio_to 10.
    ratio_from: Mapped[Decimal] = mapped_column(QUANTITY)
    ratio_to: Mapped[Decimal | None] = mapped_column(QUANTITY)
    # Parte do custo que migra para o ativo resultante (cisão).
    cost_allocation_pct: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    # Custo atribuído por ação na bonificação, quando informado pela empresa.
    cost_per_unit: Mapped[Decimal | None] = mapped_column(PRICE)
    # Premissa nossa, não dado oficial: o app sinaliza.
    is_assumption: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)


class SubscriptionOffer(IdMixin, Base):
    """Oferta de subscrição. O status de cada lote sai dos lançamentos, não daqui."""

    __tablename__ = "subscription_offer"
    __table_args__ = (CheckConstraint("price_per_unit >= 0", "price_non_negative"),)

    right_asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), unique=True)
    underlying_asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"))
    price_per_unit: Mapped[Decimal] = mapped_column(PRICE)
    # Direitos recebidos por ação possuída na data com.
    ratio: Mapped[Decimal | None] = mapped_column(QUANTITY)
    record_date: Mapped[date | None]
    deadline: Mapped[date | None]
    notes: Mapped[str | None] = mapped_column(Text)
