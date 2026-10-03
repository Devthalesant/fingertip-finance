"""Usuários do app (ADR 0002)."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin


class AppUser(IdMixin, Base):
    """Um usuário. No beta fechado, o convite é a linha criada só com o e-mail.

    A identidade do login (Google, GitHub) é preenchida no primeiro acesso.
    """

    __tablename__ = "app_user"
    __table_args__ = (UniqueConstraint("auth_provider", "auth_subject"),)

    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(120))
    # Provedor do Auth.js (ex.: "google") e o id da pessoa nele.
    auth_provider: Mapped[str | None] = mapped_column(String(32))
    auth_subject: Mapped[str | None] = mapped_column(String(255))
    # Cura o catálogo compartilhado e acessa os módulos pessoais (gastos, Pluggy).
    is_admin: Mapped[bool] = mapped_column(Boolean, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
