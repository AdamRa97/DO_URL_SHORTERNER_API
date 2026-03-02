from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Click(Base):
    __tablename__ = "clicks"

    id: Mapped[int] = mapped_column(primary_key=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("links.id"), nullable=False)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256 of IP
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    referer: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    clicked_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        index=True,
        nullable=False,
    )

    link: Mapped["Link"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="clicks",
    )
