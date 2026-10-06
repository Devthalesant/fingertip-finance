"""índices nas referências entre lançamentos (ADR 0004, teste de volume)

Revision ID: 44c3abfdd4b8
Revises: d29a1ab84532
Create Date: 2026-10-06 12:00:00.000000

Apagar um lançamento obriga o Postgres a procurar quem aponta para ele
(related_entry_id, duplicate_of_id). Sem índice, varre a tabela a cada linha apagada; o
ledger é refeito a cada importação. No teste de volume, o 2º upload caiu de 26,7 s para
14,8 s. Só cria índices: nenhuma coluna ou dado muda.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "44c3abfdd4b8"
down_revision: str | Sequence[str] | None = "d29a1ab84532"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(op.f("ix_ledger_entry_related_entry_id"), "ledger_entry", ["related_entry_id"])
    op.create_index(op.f("ix_ledger_entry_duplicate_of_id"), "ledger_entry", ["duplicate_of_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ledger_entry_duplicate_of_id"), table_name="ledger_entry")
    op.drop_index(op.f("ix_ledger_entry_related_entry_id"), table_name="ledger_entry")
