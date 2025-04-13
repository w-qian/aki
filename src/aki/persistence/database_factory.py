"""
Factory class for creating database manager instances.
"""

import asyncio
import logging
import os
from enum import Enum
from typing import Optional, Type

from aki.persistence.database_manager import DatabaseManager
from aki.persistence.postgres_manager import PostgresManager
from aki.persistence.sqlite_manager import SQLiteManager


class DatabaseType(Enum):
    """Enumeration of supported database types"""

    POSTGRES = "postgres"
    SQLITE = "sqlite"


class DatabaseFactory:
    _managers: dict[DatabaseType, Type[DatabaseManager]] = {
        DatabaseType.POSTGRES: PostgresManager,
        DatabaseType.SQLITE: SQLiteManager,
    }

    @classmethod
    def create(cls) -> Optional[DatabaseManager]:
        db_type_str = os.getenv("AKI_DATA_SOURCE", "").lower()
        if not db_type_str or db_type_str not in [db.value for db in DatabaseType]:
            logging.info(
                "History feature disabled. Please specify database source in AKI_DATA_SOURCE in ~/.aki/.env"
            )
            return None
        db_type = DatabaseType(db_type_str)
        if db_type in cls._managers:
            manager_class = cls._managers[db_type]
            return manager_class()
        else:
            logging.warning(f"No database manager registered for type '{db_type_str}'")
            return None


db_manager = None
chat_history_enabled = os.getenv("AKI_CHAT_HISTORY_ENABLED", "false").lower() == "true"
if chat_history_enabled:
    db_manager = DatabaseFactory.create()
    if db_manager:
        asyncio.run(db_manager.init_db())
