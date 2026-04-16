from collections.abc import AsyncGenerator
from datetime import datetime
import uuid

from fastapi import Depends
from fastapi_users_db_sqlalchemy import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
    SQLAlchemyUserDatabase,
)
from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# ✅ ADDED (important for Supabase pooler)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


settings = get_settings()


class Base(DeclarativeBase):
    pass


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    __tablename__ = "oauth_account"


class User(SQLAlchemyBaseUserTableUUID, Base):
    # Changed from "users" to "user" to fix the ForeignKey error
    __tablename__ = "user" 

    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship("OAuthAccount", lazy="joined")
    watchlist_pins: Mapped[list["WatchlistPin"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class WatchlistPin(Base):
    __tablename__ = "watchlist_pins"
    __table_args__ = (
        UniqueConstraint("user_id", "strike_price", name="uq_watchlist_pin_user_strike"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Pointed to "user.id" to match the change above
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    strike_price: Mapped[float] = mapped_column(Float, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="watchlist_pins")


# ✅ FIXED ENGINE CONFIG (DO NOT REMOVE ANYTHING BELOW)
engine = create_async_engine(
    settings.database_url,
    future=True,
    poolclass=NullPool,  # required for Supabase pooler
    pool_pre_ping=True,
    connect_args={
        "statement_cache_size": 0  # fixes asyncpg crash
    }
)

async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def create_db_and_tables() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)) -> AsyncGenerator:
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)
