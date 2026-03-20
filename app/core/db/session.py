from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.engine import AsyncSessionFactory


# -----------------------------------------------------------------------------
# get_db — FastAPI dependency
#
# Usage in any route:
#   async def my_route(db: AsyncSession = Depends(get_db)):
#
# Flow:
#   1. Opens a new AsyncSession from the factory
#   2. Yields it to the route handler
#   3. Commits if the handler completes successfully
#   4. Rolls back if any exception is raised
#   5. Always closes the session in finally block
#
# Note: commit() here is a convenience — for routes that only read data
# the commit is a no-op. For write operations the service layer can also
# call await session.flush() to send SQL without committing, and let
# get_db handle the final commit.
# -----------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
