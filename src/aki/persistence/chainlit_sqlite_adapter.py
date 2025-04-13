import json
from typing import Dict, List, Optional

from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.data.storage_clients.base import BaseStorageClient
from chainlit.element import ElementDict
from chainlit.logger import logger
from chainlit.types import (
    ThreadDict,
)


class ChainlitSQLiteAdapter(SQLAlchemyDataLayer):
    """
    Custom adapter for Chainlit to work with SQLite databases.
    This class overrides the methods that use PostgreSQL-specific ON CONFLICT syntax
    with SQLite-compatible INSERT OR REPLACE syntax.
    """

    def __init__(
        self,
        conninfo: str,
        ssl_require: bool = False,
        storage_provider: BaseStorageClient | None = None,
        user_thread_limit: int | None = 1000,
        show_logger: bool | None = False,
    ):
        super().__init__(
            conninfo=conninfo,
            ssl_require=ssl_require,
            storage_provider=storage_provider,
            user_thread_limit=user_thread_limit,
            show_logger=show_logger,
        )

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ):
        if self.show_logger:
            logger.info(f"SQLAlchemy: update_thread, thread_id={thread_id}")

        user_identifier = None
        if user_id:
            user_identifier = await self._get_user_identifer_by_id(user_id)

        data = {
            "id": thread_id,
            "createdAt": (
                await self.get_current_timestamp() if metadata is None else None
            ),
            "name": (
                name
                if name is not None
                else (metadata.get("name") if metadata and "name" in metadata else None)
            ),
            "userId": user_id,
            "userIdentifier": user_identifier,
            "tags": json.dumps(tags) if tags else None,
            "metadata": json.dumps(metadata) if metadata else None,
        }
        parameters = {
            key: value for key, value in data.items() if value is not None
        }  # Remove keys with None values
        columns = ", ".join(f'"{key}"' for key in parameters.keys())
        values = ", ".join(f":{key}" for key in parameters.keys())
        updates = ", ".join(
            f'"{key}" = EXCLUDED."{key}"' for key in parameters.keys() if key != "id"
        )
        query = f"""
            INSERT INTO threads ({columns})
            VALUES ({values})
            ON CONFLICT ("id") DO UPDATE
            SET {updates};
        """
        await self.execute_sql(query=query, parameters=parameters)

    async def get_all_user_threads(
        self, user_id: Optional[str] = None, thread_id: Optional[str] = None
    ) -> Optional[List[ThreadDict]]:
        threads = await super().get_all_user_threads(user_id, thread_id)
        return (
            None
            if threads is None
            else [
                {
                    **thread,
                    "tags": json.loads(thread["tags"]),
                    "metadata": json.loads(
                        thread["metadata"]
                    ),  # Convert metadata back to dict
                }
                for thread in threads
            ]
        )

    async def get_element(
        self, thread_id: str, element_id: str
    ) -> Optional["ElementDict"]:
        # blob_storage_client is not implemented
        return None

    async def create_element(self, element):
        # blob_storage_client is not implemented
        return

    async def delete_element(self, element_id: str, thread_id: Optional[str] = None):
        # blob_storage_client is not implemented
        return
