import asyncio
import logging
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncContextManager, Optional

import sqlparse
from chainlit.data.chainlit_data_layer import ChainlitDataLayer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Create a logger specific to the database manager
logger = logging.getLogger("aki.persistence.database_manager")


class DatabaseManager(ABC):

    def __init__(self):
        self._engine = None
        self._async_session_local = None
        self._async_database_url = None
        self._setup_database_url()

    @abstractmethod
    def _setup_database_url(self):
        pass

    @abstractmethod
    def _get_sql_schema_filename(self):
        pass

    @staticmethod
    def _split_sql_statements(sql_content: str) -> list[str]:
        """Split SQL script into executable statements."""
        return [stmt.strip() for stmt in sqlparse.split(sql_content) if stmt.strip()]

    async def _initialize_schema(self) -> None:
        """Initialize the database schema using SQL statements."""
        logger.debug("Initializing database schema...")
        schema_path = Path(__file__).parent / self._get_sql_schema_filename()

        try:
            with open(schema_path, "r") as file:
                sql_content = file.read()
        except Exception as e:
            logger.error(f"Error reading schema file: {e}")
            return

        # Split into individual statements
        statements = self._split_sql_statements(sql_content)
        async with self.get_session() as session:
            try:
                async with session.begin():
                    for statement in statements:
                        await session.execute(text(statement))
                await session.commit()
                logger.info("Database tables are set up.")
            except Exception as e:
                await session.rollback()
                logger.error(f"Error initializing database: {e}")
                # Log the problematic statement
                if "statement" in locals():
                    logger.error(f"Failed statement: {statement}")

    @asynccontextmanager
    async def get_session(self) -> AsyncContextManager[AsyncSession]:
        _, _async_session_local = self._get_engine()
        async with _async_session_local() as session:
            try:
                yield session
            finally:
                await session.close()

    def _get_engine(self):
        """Lazily initialize and return engine and session maker."""
        if self._engine is None:
            self._engine = create_async_engine(
                self._async_database_url,
                pool_recycle=1800,  # Recycle connections after 30 minutes
                pool_pre_ping=True,  # Verify connections before use
            )
            self._async_session_local = sessionmaker(
                bind=self._engine, class_=AsyncSession, expire_on_commit=False
            )
        return self._engine, self._async_session_local

    async def _async_shutdown_engine(self):
        """Properly dispose of the database engine during shutdown."""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None

    def shutdown(self):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    self._async_shutdown_engine()
                )  # Fire and forget (may not complete on exit)
            else:
                asyncio.run(
                    self._async_shutdown_engine()
                )  # Safe way to run the async function synchronously
        except Exception as e:
            logger.error(f"Error during database engine shutdown: {e}")

    @abstractmethod
    async def init_db(self) -> None:
        """Initialize the database with required schema"""
        pass

    @abstractmethod
    def get_adapter(self) -> Optional[ChainlitDataLayer]:
        """Return a Chainlit adapter for the database or None if creation fails"""
        pass

    @property
    @abstractmethod
    def db_type(self) -> str:
        """Return the database type identifier"""
        pass
