"""Base dos modelos SQLAlchemy e tipos compartilhados (ver ADR 0001)."""

import enum

from sqlalchemy import BigInteger, Enum, ForeignKey, Identity, MetaData, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Nomes previsíveis para constraints e índices. Sem isso o Postgres inventa nomes
# e o Alembic não consegue apagar ou alterar a constraint numa migration futura.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Dinheiro como vem na fonte (centavos). Quantidade e preço unitário com mais casas:
# ação fracionada no exterior e PU de título de renda fixa.
MONEY = Numeric(18, 2)
QUANTITY = Numeric(28, 10)
PRICE = Numeric(28, 10)
RATE = Numeric(18, 8)
CURRENCY = String(3)


def enum_column(enum_cls: type[enum.Enum]) -> Enum:
    """Enum guardado como texto + CHECK, não como tipo nativo do Postgres.

    Adicionar ou remover um valor vira uma migration simples (troca o CHECK).
    """
    return Enum(
        enum_cls,
        native_enum=False,
        create_constraint=True,
        length=32,
        name=enum_cls.__name__.lower(),
        values_callable=lambda cls: [member.value for member in cls],
    )


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {int: BigInteger}


class IdMixin:
    # sort_order negativo: o id vem como primeira coluna da tabela.
    id: Mapped[int] = mapped_column(Identity(), primary_key=True, sort_order=-1)


class UserOwnedMixin:
    """Linha que pertence a um usuário (ADR 0002). Toda consulta filtra por esta coluna."""

    user_id: Mapped[int] = mapped_column(ForeignKey("app_user.id"), index=True, sort_order=-1)
