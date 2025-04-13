import json
import logging
from dataclasses import asdict
from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from aki.chat.base.base_profile import BaseState
from aki.chat.base.environment_details import EnvironmentDetails
from aki.persistence.models import State


class StateDAL:
    MESSAGE_TYPE_MAPPING = {
        "human": HumanMessage,
        "ai": AIMessage,
        "tool": ToolMessage,
        "system": SystemMessage,
    }

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.dialect = self.db_session.bind.dialect.name

    async def upsert_state(self, thread_id: str, state: BaseState) -> None:
        """Upsert a state based on thread_id using dialect-specific optimizations."""
        try:
            serialized_state = self._serialize_state(state)
            insert_fn = pg_insert if self.dialect == "postgresql" else sqlite_insert
            stmt = (
                insert_fn(State)
                .values(threadId=thread_id, state=serialized_state)
                .on_conflict_do_update(
                    index_elements=["threadId"],  # Unique constraint field
                    set_={"state": serialized_state},
                )
            )
            await self.db_session.execute(stmt)
            await self.db_session.commit()
        except Exception as e:
            logging.error(f"Failed to upsert_state: {e}", exc_info=True)
            return None

    def _serialize_state(self, state: BaseState) -> dict[str, Any]:
        """Serialize state object to dictionary format."""
        serialized_state = {}

        for key, value in state.items():
            if isinstance(value, EnvironmentDetails):
                env_dict = asdict(value)  # Convert EnvironmentDetails to a dictionary
                serialized_state[key] = env_dict
            elif key == "messages":
                serialized_state[key] = [
                    msg.model_dump() for msg in value if msg is not None
                ]
            else:
                serialized_state[key] = value

        return serialized_state

    async def get_state(self, thread_id: str) -> BaseState | None:
        """Fetch and deserialize state by thread_id."""
        result = await self.db_session.get(State, thread_id)
        if not result:
            return None

        state_data = result.state
        if isinstance(state_data, str):
            state_data = json.loads(state_data)

        return self._deserialize_state(state_data)

    def _deserialize_state(self, state_data: dict[str, Any]) -> BaseState:
        """Deserialize state data into BaseState object."""
        state_dict = dict(state_data)

        if "messages" in state_dict:
            state_dict["messages"] = self._deserialize_messages(state_dict["messages"])

        # Convert EnvironmentDetails and TokenManager back into objects
        if "environment" in state_dict:
            env_dict = state_dict["environment"]
            # EnvironmentDetails no longer has workspace_stats
            state_dict["environment"] = self._deserialize_dataclass(
                EnvironmentDetails, env_dict
            )

        return BaseState(**state_dict)

    def _deserialize_dataclass(self, cls: Any, data: dict[str, Any]) -> Any:
        """Convert a dictionary back into a dataclass instance."""
        if not isinstance(data, dict):
            return data

        # Filter out attributes that don't exist in the current class
        import inspect

        valid_params = inspect.signature(cls.__init__).parameters.keys()

        # Identify fields that need to be filtered out
        invalid_fields = set(data.keys()) - set(valid_params)
        if invalid_fields:
            logging.debug(
                f"Filtering out non-existent fields from {cls.__name__}: {invalid_fields}"
            )

        filtered_data = {k: v for k, v in data.items() if k in valid_params}

        return cls(**filtered_data)

    def _deserialize_messages(self, messages: list) -> list[BaseMessage]:
        """Convert stored messages back into appropriate Message objects."""
        return [
            self.MESSAGE_TYPE_MAPPING.get(msg.get("type"), BaseMessage)(**msg)
            for msg in messages
        ]
