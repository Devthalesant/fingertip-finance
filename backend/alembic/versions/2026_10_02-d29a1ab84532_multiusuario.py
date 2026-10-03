"""multiusuario (ADR 0002)

Revision ID: d29a1ab84532
Revises: d1a99da658fc
Create Date: 2026-10-02 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d29a1ab84532"
down_revision: str | Sequence[str] | None = "d1a99da658fc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tabelas com dados de cada usuário. As do catálogo (ativos, eventos, cotações) seguem
# compartilhadas.
USER_OWNED = ("account", "import_file", "raw_row", "ledger_entry", "position_snapshot")

# Unicidades que passam a valer por usuário: (tabela, nome antigo, colunas antigas).
PER_USER_UNIQUES = (
    ("account", "uq_account_institution_id_kind_label", ["institution_id", "kind", "label"]),
    ("import_file", "uq_import_file_file_sha256", ["file_sha256"]),
    ("raw_row", "uq_raw_row_source_row_hash", ["source", "row_hash"]),
)


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("auth_provider", sa.String(length=32), nullable=True),
        sa.Column("auth_subject", sa.String(length=255), nullable=True),
        sa.Column("is_admin", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_user")),
        sa.UniqueConstraint("email", name=op.f("uq_app_user_email")),
        sa.UniqueConstraint(
            "auth_provider", "auth_subject", name=op.f("uq_app_user_auth_provider_auth_subject")
        ),
    )

    # NOT NULL sem valor padrão: só funciona com as tabelas vazias, que é o caso. Se
    # houvesse dados, o Postgres recusaria e nada seria alterado.
    for table in USER_OWNED:
        op.add_column(table, sa.Column("user_id", sa.BigInteger(), nullable=False))
        op.create_foreign_key(
            op.f(f"fk_{table}_user_id_app_user"), table, "app_user", ["user_id"], ["id"]
        )
        op.create_index(op.f(f"ix_{table}_user_id"), table, ["user_id"], unique=False)

    for table, old_name, columns in PER_USER_UNIQUES:
        op.drop_constraint(old_name, table, type_="unique")
        op.create_unique_constraint(
            op.f(f"uq_{table}_user_id_{'_'.join(columns)}"), table, ["user_id", *columns]
        )

    # Ativo privado: sem dono é catálogo; com dono, só daquele usuário. Nulos iguais
    # entre si, para o catálogo não ter dois ativos com o mesmo código.
    op.add_column("asset", sa.Column("owner_user_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key(
        op.f("fk_asset_owner_user_id_app_user"), "asset", "app_user", ["owner_user_id"], ["id"]
    )
    op.drop_constraint("uq_asset_canonical_code", "asset", type_="unique")
    op.create_unique_constraint(
        op.f("uq_asset_owner_user_id_canonical_code"),
        "asset",
        ["owner_user_id", "canonical_code"],
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    op.drop_constraint("uq_asset_owner_user_id_canonical_code", "asset", type_="unique")
    op.create_unique_constraint("uq_asset_canonical_code", "asset", ["canonical_code"])
    op.drop_constraint("fk_asset_owner_user_id_app_user", "asset", type_="foreignkey")
    op.drop_column("asset", "owner_user_id")

    for table, old_name, columns in PER_USER_UNIQUES:
        op.drop_constraint(f"uq_{table}_user_id_{'_'.join(columns)}", table, type_="unique")
        op.create_unique_constraint(old_name, table, columns)

    for table in USER_OWNED:
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_constraint(f"fk_{table}_user_id_app_user", table, type_="foreignkey")
        op.drop_column(table, "user_id")

    op.drop_table("app_user")
