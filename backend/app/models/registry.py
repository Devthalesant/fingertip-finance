"""Cadastro: instituições, contas e ativos."""

from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import CURRENCY, Base, IdMixin, enum_column
from app.models.enums import (
    AccountKind,
    AssetClass,
    FixedIncomeProduct,
    Indexer,
    InstitutionKind,
    TaxRegime,
)


class Institution(IdMixin, Base):
    """Corretora ou banco, com nome canônico."""

    __tablename__ = "institution"

    name: Mapped[str] = mapped_column(String(120), unique=True)
    kind: Mapped[InstitutionKind] = mapped_column(enum_column(InstitutionKind))
    cnpj: Mapped[str | None] = mapped_column(String(14), unique=True)


class InstitutionAlias(IdMixin, Base):
    """Cada grafia do nome da instituição que aparece nos arquivos."""

    __tablename__ = "institution_alias"

    institution_id: Mapped[int] = mapped_column(ForeignKey("institution.id"))
    raw_name: Mapped[str] = mapped_column(String(200), unique=True)


class Account(IdMixin, Base):
    """Conta dentro de uma instituição (custódia, corrente, cartão)."""

    __tablename__ = "account"
    __table_args__ = (UniqueConstraint("institution_id", "kind", "label"),)

    institution_id: Mapped[int] = mapped_column(ForeignKey("institution.id"))
    kind: Mapped[AccountKind] = mapped_column(enum_column(AccountKind))
    label: Mapped[str] = mapped_column(String(80))
    currency: Mapped[str] = mapped_column(CURRENCY, default="BRL")
    # Identificador no Pluggy (v0.6).
    external_id: Mapped[str | None] = mapped_column(String(80), unique=True)


class Asset(IdMixin, Base):
    """Um ativo, identificado pelo ticker (ou código do título) canônico.

    A classe é dado cadastrado, nunca deduzida do sufixo do ticker.
    """

    __tablename__ = "asset"

    canonical_code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str | None] = mapped_column(String(200))
    asset_class: Mapped[AssetClass] = mapped_column(enum_column(AssetClass))
    currency: Mapped[str] = mapped_column(CURRENCY, default="BRL")
    # Direito ou recibo de subscrição aponta para o ativo que dá origem a ele.
    underlying_asset_id: Mapped[int | None] = mapped_column(ForeignKey("asset.id"))


class AssetAlias(IdMixin, Base):
    """Ticker antigo ou variante, com vigência. Troca de ticker não cria ativo novo."""

    __tablename__ = "asset_alias"
    __table_args__ = (
        UniqueConstraint("alias", "valid_from", postgresql_nulls_not_distinct=True),
        CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from", "period"
        ),
    )

    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"))
    alias: Mapped[str] = mapped_column(String(40))
    valid_from: Mapped[date | None]
    valid_to: Mapped[date | None]


class FixedIncomeSecurity(Base):
    """Detalhe 1:1 de um ativo de renda fixa. Cada título é um ativo próprio."""

    __tablename__ = "fixed_income_security"
    __table_args__ = (CheckConstraint("maturity_date >= issue_date", "maturity_after_issue"),)

    asset_id: Mapped[int] = mapped_column(ForeignKey("asset.id"), primary_key=True)
    issuer_institution_id: Mapped[int | None] = mapped_column(ForeignKey("institution.id"))
    product: Mapped[FixedIncomeProduct] = mapped_column(enum_column(FixedIncomeProduct))
    indexer: Mapped[Indexer] = mapped_column(enum_column(Indexer))
    # Percentual do indexador (ex.: 102 = 102% do CDI).
    rate_pct: Mapped[Decimal | None] = mapped_column(Numeric(9, 4))
    # Taxa adicional ao ano (ex.: IPCA + 6,5) ou a taxa do prefixado.
    spread_pct: Mapped[Decimal | None] = mapped_column(Numeric(9, 4))
    issue_date: Mapped[date]
    maturity_date: Mapped[date]
    # Código do título na B3, quando houver.
    external_code: Mapped[str | None] = mapped_column(String(40), unique=True)
    tax_regime: Mapped[TaxRegime] = mapped_column(enum_column(TaxRegime))
