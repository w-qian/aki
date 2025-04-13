"""Time-related tools"""

from datetime import datetime
from typing import Optional, Type
from langchain_core.tools import BaseTool
from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import BaseModel


class GetDatetimeNowTool(BaseTool):
    """Tool for getting current date and time."""

    name: str = "get_datetime_now"
    description: str = "Get current date and time."
    args_schema: Optional[Type[BaseModel]] = None  # No input parameters needed

    def _run(
        self,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Get current date and time synchronously."""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async def _arun(
        self,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Get current date and time asynchronously."""
        return self._run(run_manager=run_manager)


def create_datetime_now_tool() -> BaseTool:
    """Create and return the datetime now tool."""
    return GetDatetimeNowTool()
