"""
PostgreSQL database manager implementation.
"""

import asyncio
import os
import shutil
import subprocess
import time

import asyncpg
import logging

from chainlit.data.chainlit_data_layer import ChainlitDataLayer
from dotenv import load_dotenv

from aki.config.paths import get_env_file
from aki.persistence.database_manager import DatabaseManager

# Load environment variables
load_dotenv(get_env_file())


class PostgresManager(DatabaseManager):
    """
    PostgreSQL implementation of the DatabaseManager interface.
    """

    def _setup_database_url(self):
        # Set up connection URL
        current_user = os.getenv("USER")
        self._database_url = os.getenv("AKI_POSTGRES_URL")
        if not self._database_url:
            self._database_url = f"postgresql://{current_user}@localhost:5432/postgres"
        if "$USER" in self._database_url:
            self._database_url = self._database_url.replace("$USER", current_user)

        # Make URL available to other components
        os.environ["AKI_POSTGRES_URL"] = self._database_url

        # Create async version of URL
        self._async_database_url = self._database_url
        if "postgresql://" in self._database_url:
            self._async_database_url = self._database_url.replace(
                "postgresql://", "postgresql+asyncpg://"
            )

    @property
    def db_type(self) -> str:
        return PostgresManager.__name__

    async def init_db(self) -> None:
        """Initialize PostgreSQL and database schema."""
        await self._start_postgres()  # Ensures Postgres is installed & running
        await self._initialize_schema()  # Sets up database tables

    async def _start_postgres(self) -> None:
        """Start PostgreSQL asynchronously and wait for it to fully start."""
        await self._ensure_postgresql_installed()
        if not await self._is_postgres_running():
            logging.info("Starting PostgreSQL...")
            subprocess.run(["brew", "services", "start", "postgresql"], check=True)
            await self._wait_for_postgres_start()

    async def _ensure_postgresql_installed(self) -> None:
        """Check if PostgreSQL is installed, and install it if not."""
        if shutil.which("psql") is None:
            logging.info("PostgreSQL not found, installing...")
            process = await asyncio.create_subprocess_exec(
                "brew", "install", "postgresql"
            )
            await process.communicate()

    async def _is_postgres_running(self) -> bool:
        """Check if PostgreSQL is running."""
        try:
            conn = await asyncpg.connect(self._database_url)
            await conn.close()
            logging.debug("PostgreSQL is running.")
            return True
        except Exception as e:
            logging.error(f"Error connecting to database: {e}")
            return False

    async def _wait_for_postgres_start(
        self, max_retries=5, initial_delay=1, max_delay=30, total_timeout=120
    ) -> bool:
        """Wait for PostgreSQL to become available using exponential backoff."""
        delay = initial_delay
        start_time = time.time()
        for attempt in range(1, max_retries + 1):
            if time.time() - start_time > total_timeout:
                return False
            if await self._is_postgres_running():
                return True
            await asyncio.sleep(min(delay, max_delay))
            delay *= 2  # Exponential backoff
        logging.error("PostgreSQL failed to start after multiple attempts.")
        return False

    def _get_sql_schema_filename(self):
        return "database_schema.sql"

    def get_adapter(self) -> ChainlitDataLayer:
        """Return a Chainlit data layer for PostgreSQL."""
        try:
            return ChainlitDataLayer(database_url=self._database_url)
        except Exception as e:
            logging.error(f"Failed to create PostgreSQL adapter: {e}", exc_info=True)
            return None
