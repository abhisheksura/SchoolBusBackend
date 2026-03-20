from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from app.core.config import settings


# -----------------------------------------------------------------------------
# Async Engine
# Created once at startup and reused across all requests.
# pool_pre_ping=True validates connections before checkout —
# essential for async pools to detect stale/dropped DB connections.
# -----------------------------------------------------------------------------
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
)


# -----------------------------------------------------------------------------
# Async Session Factory
#
# expire_on_commit=False — keeps ORM objects usable after commit without
# triggering lazy loads (lazy loads raise MissingGreenlet in async context).
#
# autoflush=False — prevents SQLAlchemy from silently issuing SQL before
# every query. We flush explicitly via await session.flush() when needed.
#
# autocommit=False — we manage transactions manually via get_db().
# -----------------------------------------------------------------------------
AsyncSessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)
