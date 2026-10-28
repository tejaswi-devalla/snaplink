from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ShortLink(Base):
    __tablename__ = "short_links"
    __table_args__ = (
        UniqueConstraint("code", name="uq_short_links_code"),
        Index("ix_short_links_created_at", "created_at"),
        Index("ix_short_links_expires_at", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    management_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    click_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_clicked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")


class AbuseReport(Base):
    __tablename__ = "abuse_reports"
    __table_args__ = (
        Index("ix_abuse_reports_status_created_at", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(
        String(32), ForeignKey("short_links.code", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    details: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open", server_default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
