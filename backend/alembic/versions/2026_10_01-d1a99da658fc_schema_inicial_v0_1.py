"""schema inicial v0.1

Revision ID: d1a99da658fc
Revises:
Create Date: 2026-10-01 18:50:50.720527

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d1a99da658fc"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Gerada a partir de app/models (ver ADR 0001). Enums viram texto + CHECK nomeado.
    op.create_table(
        "asset",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("canonical_code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("underlying_asset_id", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "asset_class IN ('ACAO', 'FII', 'ETF', 'BDR', 'UNIT', 'RENDA_FIXA', 'TESOURO', 'DIREITO_SUBSCRICAO', 'RECIBO_SUBSCRICAO', 'ACAO_EXTERIOR', 'ETF_EXTERIOR', 'A_CLASSIFICAR')",
            name=op.f("ck_asset_assetclass"),
        ),
        sa.ForeignKeyConstraint(
            ["underlying_asset_id"], ["asset.id"], name=op.f("fk_asset_underlying_asset_id_asset")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset")),
        sa.UniqueConstraint("canonical_code", name=op.f("uq_asset_canonical_code")),
    )
    op.create_table(
        "fx_rate",
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("buy", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("sell", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.PrimaryKeyConstraint("currency", "rate_date", name=op.f("pk_fx_rate")),
    )
    op.create_table(
        "import_file",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('B3_MOVIMENTACAO', 'B3_CONSOLIDADO_MENSAL', 'B3_CONSOLIDADO_ANUAL', 'NOMAD_EXTRATO', 'NOMAD_IR')",
            name=op.f("ck_import_file_datasource"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_file")),
        sa.UniqueConstraint("file_sha256", name=op.f("uq_import_file_file_sha256")),
    )
    op.create_table(
        "institution",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("cnpj", sa.String(length=14), nullable=True),
        sa.CheckConstraint(
            "kind IN ('BROKER', 'BANK', 'FOREIGN_BROKER')",
            name=op.f("ck_institution_institutionkind"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institution")),
        sa.UniqueConstraint("cnpj", name=op.f("uq_institution_cnpj")),
        sa.UniqueConstraint("name", name=op.f("uq_institution_name")),
    )
    op.create_table(
        "account",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("institution_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("external_id", sa.String(length=80), nullable=True),
        sa.CheckConstraint(
            "kind IN ('CUSTODY', 'CHECKING', 'CREDIT_CARD')", name=op.f("ck_account_accountkind")
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institution.id"],
            name=op.f("fk_account_institution_id_institution"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account")),
        sa.UniqueConstraint("external_id", name=op.f("uq_account_external_id")),
        sa.UniqueConstraint(
            "institution_id", "kind", "label", name=op.f("uq_account_institution_id_kind_label")
        ),
    )
    op.create_table(
        "asset_alias",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("alias", sa.String(length=40), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name=op.f("ck_asset_alias_period"),
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["asset.id"], name=op.f("fk_asset_alias_asset_id_asset")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset_alias")),
        sa.UniqueConstraint(
            "alias",
            "valid_from",
            name=op.f("uq_asset_alias_alias_valid_from"),
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_table(
        "corporate_event",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("source_asset_id", sa.BigInteger(), nullable=False),
        sa.Column("target_asset_id", sa.BigInteger(), nullable=True),
        sa.Column("ratio_from", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("ratio_to", sa.Numeric(precision=28, scale=10), nullable=True),
        sa.Column("cost_allocation_pct", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("cost_per_unit", sa.Numeric(precision=28, scale=10), nullable=True),
        sa.Column("is_assumption", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "event_type IN ('DESDOBRO', 'GRUPAMENTO', 'BONIFICACAO', 'TROCA_TICKER', 'CISAO', 'INCORPORACAO', 'CONVERSAO_RECIBO')",
            name=op.f("ck_corporate_event_corporateeventtype"),
        ),
        sa.CheckConstraint(
            "cost_allocation_pct IS NULL OR cost_allocation_pct BETWEEN 0 AND 100",
            name=op.f("ck_corporate_event_cost_allocation_range"),
        ),
        sa.CheckConstraint(
            "ratio_from > 0 AND (ratio_to IS NULL OR ratio_to > 0)",
            name=op.f("ck_corporate_event_ratio_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["source_asset_id"], ["asset.id"], name=op.f("fk_corporate_event_source_asset_id_asset")
        ),
        sa.ForeignKeyConstraint(
            ["target_asset_id"], ["asset.id"], name=op.f("fk_corporate_event_target_asset_id_asset")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_corporate_event")),
    )
    op.create_table(
        "fixed_income_security",
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("issuer_institution_id", sa.BigInteger(), nullable=True),
        sa.Column("product", sa.String(length=32), nullable=False),
        sa.Column("indexer", sa.String(length=32), nullable=False),
        sa.Column("rate_pct", sa.Numeric(precision=9, scale=4), nullable=True),
        sa.Column("spread_pct", sa.Numeric(precision=9, scale=4), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("maturity_date", sa.Date(), nullable=False),
        sa.Column("external_code", sa.String(length=40), nullable=True),
        sa.Column("tax_regime", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "indexer IN ('CDI', 'IPCA', 'SELIC', 'PRE')",
            name=op.f("ck_fixed_income_security_indexer"),
        ),
        sa.CheckConstraint(
            "product IN ('CDB', 'LCA', 'LCI', 'CRI', 'CRA', 'DEBENTURE', 'TESOURO_SELIC', 'TESOURO_IPCA', 'TESOURO_PREFIXADO')",
            name=op.f("ck_fixed_income_security_fixedincomeproduct"),
        ),
        sa.CheckConstraint(
            "tax_regime IN ('REGRESSIVO', 'ISENTO')",
            name=op.f("ck_fixed_income_security_taxregime"),
        ),
        sa.CheckConstraint(
            "maturity_date >= issue_date",
            name=op.f("ck_fixed_income_security_maturity_after_issue"),
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["asset.id"], name=op.f("fk_fixed_income_security_asset_id_asset")
        ),
        sa.ForeignKeyConstraint(
            ["issuer_institution_id"],
            ["institution.id"],
            name=op.f("fk_fixed_income_security_issuer_institution_id_institution"),
        ),
        sa.PrimaryKeyConstraint("asset_id", name=op.f("pk_fixed_income_security")),
        sa.UniqueConstraint("external_code", name=op.f("uq_fixed_income_security_external_code")),
    )
    op.create_table(
        "institution_alias",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("institution_id", sa.BigInteger(), nullable=False),
        sa.Column("raw_name", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institution.id"],
            name=op.f("fk_institution_alias_institution_id_institution"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institution_alias")),
        sa.UniqueConstraint("raw_name", name=op.f("uq_institution_alias_raw_name")),
    )
    op.create_table(
        "price",
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("close", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"], name=op.f("fk_price_asset_id_asset")),
        sa.PrimaryKeyConstraint("asset_id", "price_date", name=op.f("pk_price")),
    )
    op.create_table(
        "raw_row",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("import_file_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("row_number", sa.BigInteger(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("occurrence_index", sa.BigInteger(), nullable=False),
        sa.Column("row_hash", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "source IN ('B3_MOVIMENTACAO', 'B3_CONSOLIDADO_MENSAL', 'B3_CONSOLIDADO_ANUAL', 'NOMAD_EXTRATO', 'NOMAD_IR')",
            name=op.f("ck_raw_row_datasource"),
        ),
        sa.ForeignKeyConstraint(
            ["import_file_id"],
            ["import_file.id"],
            name=op.f("fk_raw_row_import_file_id_import_file"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_raw_row")),
        sa.UniqueConstraint(
            "import_file_id", "row_number", name=op.f("uq_raw_row_import_file_id_row_number")
        ),
        sa.UniqueConstraint("source", "row_hash", name=op.f("uq_raw_row_source_row_hash")),
    )
    op.create_table(
        "subscription_offer",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("right_asset_id", sa.BigInteger(), nullable=False),
        sa.Column("underlying_asset_id", sa.BigInteger(), nullable=False),
        sa.Column("price_per_unit", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("ratio", sa.Numeric(precision=28, scale=10), nullable=True),
        sa.Column("record_date", sa.Date(), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "price_per_unit >= 0", name=op.f("ck_subscription_offer_price_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["right_asset_id"],
            ["asset.id"],
            name=op.f("fk_subscription_offer_right_asset_id_asset"),
        ),
        sa.ForeignKeyConstraint(
            ["underlying_asset_id"],
            ["asset.id"],
            name=op.f("fk_subscription_offer_underlying_asset_id_asset"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscription_offer")),
        sa.UniqueConstraint("right_asset_id", name=op.f("uq_subscription_offer_right_asset_id")),
    )
    op.create_table(
        "ledger_entry",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("raw_row_id", sa.BigInteger(), nullable=True),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("parser_version", sa.String(length=20), nullable=True),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("settlement_date", sa.Date(), nullable=True),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=28, scale=10), nullable=True),
        sa.Column("unit_price", sa.Numeric(precision=28, scale=10), nullable=True),
        sa.Column("gross_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("fees", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("tax_withheld", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("affects_position", sa.Boolean(), nullable=False),
        sa.Column("corporate_event_id", sa.BigInteger(), nullable=True),
        sa.Column("subscription_offer_id", sa.BigInteger(), nullable=True),
        sa.Column("related_entry_id", sa.BigInteger(), nullable=True),
        sa.Column("duplicate_of_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "flags",
            postgresql.ARRAY(sa.String(length=40)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(origin = 'IMPORT' AND raw_row_id IS NOT NULL AND parser_version IS NOT NULL) OR (origin = 'MANUAL' AND raw_row_id IS NULL)",
            name=op.f("ck_ledger_entry_origin_matches_source"),
        ),
        sa.CheckConstraint("direction IN ('IN', 'OUT')", name=op.f("ck_ledger_entry_direction")),
        sa.CheckConstraint(
            "entry_type IN ('COMPRA', 'VENDA', 'RESGATE', 'ALUGUEL_SAIDA', 'ALUGUEL_RETORNO', 'ALUGUEL_REGISTRO', 'ALUGUEL_REMUNERACAO', 'REEMBOLSO_ALUGUEL', 'RENDIMENTO', 'JCP', 'DIVIDENDO', 'JUROS', 'AMORTIZACAO', 'BONIFICACAO', 'DESDOBRO', 'GRUPAMENTO', 'ATUALIZACAO', 'INCORPORACAO', 'FRACAO_BAIXA', 'LEILAO_FRACAO', 'SUBSCRICAO_SOLICITADA', 'SUBSCRICAO_EXERCIDA', 'SUBSCRICAO_RECIBO', 'DIREITO_RECEBIDO', 'DIREITO_CEDIDO', 'DIREITO_CESSAO_SOLICITADA', 'DIREITO_EXPIRADO', 'TRANSFERENCIA_CUSTODIA', 'EVENTO_EXCLUIDO')",
            name=op.f("ck_ledger_entry_entrytype"),
        ),
        sa.CheckConstraint(
            "origin IN ('IMPORT', 'MANUAL')", name=op.f("ck_ledger_entry_entryorigin")
        ),
        sa.CheckConstraint(
            "duplicate_of_id <> id", name=op.f("ck_ledger_entry_not_duplicate_of_itself")
        ),
        sa.CheckConstraint(
            "quantity IS NULL OR quantity >= 0", name=op.f("ck_ledger_entry_quantity_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_ledger_entry_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["asset.id"], name=op.f("fk_ledger_entry_asset_id_asset")
        ),
        sa.ForeignKeyConstraint(
            ["corporate_event_id"],
            ["corporate_event.id"],
            name=op.f("fk_ledger_entry_corporate_event_id_corporate_event"),
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_of_id"],
            ["ledger_entry.id"],
            name=op.f("fk_ledger_entry_duplicate_of_id_ledger_entry"),
        ),
        sa.ForeignKeyConstraint(
            ["raw_row_id"], ["raw_row.id"], name=op.f("fk_ledger_entry_raw_row_id_raw_row")
        ),
        sa.ForeignKeyConstraint(
            ["related_entry_id"],
            ["ledger_entry.id"],
            name=op.f("fk_ledger_entry_related_entry_id_ledger_entry"),
        ),
        sa.ForeignKeyConstraint(
            ["subscription_offer_id"],
            ["subscription_offer.id"],
            name=op.f("fk_ledger_entry_subscription_offer_id_subscription_offer"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ledger_entry")),
    )
    op.create_index(
        "ix_ledger_entry_asset_id_trade_date",
        "ledger_entry",
        ["asset_id", "trade_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ledger_entry_raw_row_id"), "ledger_entry", ["raw_row_id"], unique=False
    )
    op.create_table(
        "position_snapshot",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("import_file_id", sa.BigInteger(), nullable=False),
        sa.Column("ref_date", sa.Date(), nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("asset_id", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=28, scale=10), nullable=False),
        sa.Column("reported_price", sa.Numeric(precision=28, scale=10), nullable=True),
        sa.Column("reported_value", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("reported_cost", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.ForeignKeyConstraint(
            ["account_id"], ["account.id"], name=op.f("fk_position_snapshot_account_id_account")
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"], ["asset.id"], name=op.f("fk_position_snapshot_asset_id_asset")
        ),
        sa.ForeignKeyConstraint(
            ["import_file_id"],
            ["import_file.id"],
            name=op.f("fk_position_snapshot_import_file_id_import_file"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_position_snapshot")),
        sa.UniqueConstraint(
            "import_file_id",
            "account_id",
            "asset_id",
            name=op.f("uq_position_snapshot_import_file_id_account_id_asset_id"),
        ),
    )


def downgrade() -> None:
    op.drop_table("position_snapshot")
    op.drop_table("ledger_entry")
    op.drop_table("subscription_offer")
    op.drop_table("raw_row")
    op.drop_table("price")
    op.drop_table("institution_alias")
    op.drop_table("fixed_income_security")
    op.drop_table("corporate_event")
    op.drop_table("asset_alias")
    op.drop_table("account")
    op.drop_table("institution")
    op.drop_table("import_file")
    op.drop_table("fx_rate")
    op.drop_table("asset")
