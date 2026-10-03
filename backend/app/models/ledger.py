"""Importação e ledger: as três camadas do ADR 0001."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    CURRENCY,
    MONEY,
    PRICE,
    QUANTITY,
    Base,
    IdMixin,
    UserOwnedMixin,
    enum_column,
)
from app.models.enums import DataSource, Direction, EntryOrigin, EntryType


class ImportFile(IdMixin, UserOwnedMixin, Base):
    """Um arquivo importado. O mesmo arquivo (mesmo SHA-256) não entra duas vezes."""

    __tablename__ = "import_file"
    __table_args__ = (UniqueConstraint("user_id", "file_sha256"),)

    source: Mapped[DataSource] = mapped_column(enum_column(DataSource))
    file_name: Mapped[str] = mapped_column(String(255))
    file_sha256: Mapped[str] = mapped_column(String(64))
    period_start: Mapped[date | None]
    period_end: Mapped[date | None]
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RawRow(IdMixin, UserOwnedMixin, Base):
    """Linha original do arquivo, imutável.

    row_hash = conteúdo normalizado + fonte + índice de ocorrência daquele conteúdo no
    arquivo. Reimportar um período sobreposto não duplica, e linhas idênticas legítimas
    (mesmo dia, ativo, tipo e valor) não se perdem. A unicidade é por usuário: duas
    pessoas podem ter a mesma linha no extrato.
    """

    __tablename__ = "raw_row"
    __table_args__ = (
        UniqueConstraint("user_id", "source", "row_hash"),
        UniqueConstraint("import_file_id", "row_number"),
    )

    import_file_id: Mapped[int] = mapped_column(ForeignKey("import_file.id"))
    # Repetido do arquivo para a unicidade do hash valer por fonte.
    source: Mapped[DataSource] = mapped_column(enum_column(DataSource))
    row_number: Mapped[int]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    occurrence_index: Mapped[int]
    row_hash: Mapped[str] = mapped_column(String(64))


class LedgerEntry(IdMixin, UserOwnedMixin, Base):
    """Lançamento normalizado, lido pelo motor de cálculo.

    Derivado das linhas brutas (pode ser apagado e regerado) ou lançado à mão.
    Não guarda quantidade acumulada nem PM: isso é sempre calculado.
    """

    __tablename__ = "ledger_entry"
    __table_args__ = (
        CheckConstraint(
            "(origin = 'IMPORT' AND raw_row_id IS NOT NULL AND parser_version IS NOT NULL)"
            " OR (origin = 'MANUAL' AND raw_row_id IS NULL)",
            "origin_matches_source",
        ),
        CheckConstraint("quantity IS NULL OR quantity >= 0", "quantity_non_negative"),
        CheckConstraint("duplicate_of_id <> id", "not_duplicate_of_itself"),
        Index("ix_ledger_entry_asset_id_trade_date", "asset_id", "trade_date"),
        Index(None, "raw_row_id"),
    )

    raw_row_id: Mapped[int | None] = mapped_column(ForeignKey("raw_row.id"))
    origin: Mapped[EntryOrigin] = mapped_column(enum_column(EntryOrigin))
    parser_version: Mapped[str | None] = mapped_column(String(20))
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"))
    trade_date: Mapped[date]
    settlement_date: Mapped[date | None]
    entry_type: Mapped[EntryType] = mapped_column(enum_column(EntryType))
    direction: Mapped[Direction] = mapped_column(enum_column(Direction))
    quantity: Mapped[Decimal | None] = mapped_column(QUANTITY)
    unit_price: Mapped[Decimal | None] = mapped_column(PRICE)
    gross_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    # Corretagem e emolumentos (notas de corretagem, v0.3).
    fees: Mapped[Decimal | None] = mapped_column(MONEY)
    # IR retido na fonte (JCP, dividendos no exterior).
    tax_withheld: Mapped[Decimal | None] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(CURRENCY, default="BRL")
    affects_position: Mapped[bool] = mapped_column(Boolean)
    corporate_event_id: Mapped[int | None] = mapped_column(ForeignKey("corporate_event.id"))
    subscription_offer_id: Mapped[int | None] = mapped_column(ForeignKey("subscription_offer.id"))
    # Par do aluguel: o retorno aponta para a saída.
    related_entry_id: Mapped[int | None] = mapped_column(ForeignKey("ledger_entry.id"))
    # Mesmo lançamento em outra fonte; o motor ignora a duplicata.
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("ledger_entry.id"))
    # Premissas a sinalizar no app (ex.: COST_ASSUMED_ZERO).
    flags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), server_default=text("'{}'"))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
