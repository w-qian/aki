from typing import List, Optional, Dict
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
import chainlit as cl
import uuid
import asyncio


class TaskData(BaseModel):
    """Data model for a single task."""

    title: str = Field(description="The title of the task")
    status: Optional[str] = Field(
        default="ready", description="Task status: ready, running, done, or failed"
    )
    message_id: Optional[str] = Field(
        default=None, description="ID of a chat message to link to this task"
    )


class TaskListInput(BaseModel):
    """Input for managing task lists."""

    title: Optional[str] = Field(
        default=None,
        description="Title of the task list (required when creating a new list)",
    )
    tasklist_id: Optional[str] = Field(
        default=None, description="ID of existing task list (required when updating)"
    )
    status: Optional[str] = Field(
        default="ready", description="Status message for the task list"
    )
    tasks: List[TaskData] = Field(
        description="List of tasks to create or update", min_length=1
    )


# Global registry for task lists
tasklist_registry: Dict[str, cl.TaskList] = {}


class TaskListTool(BaseTool):
    """Tool for managing task lists in Chainlit chat interface."""

    name: str = "tasklist"
    description: str = """Use this tool to break down complex tasks and track progress in the chat interface.

Task Status Management:
IMPORTANT: Always mark tasks as 'running' before starting work on them!
- Multiple tasks can be running simultaneously
- When starting a new tasklist, mark the first 1-3 tasks you plan to work on as 'running'
- Update task status to 'running' before beginning any new task
- Only mark tasks as 'done' when fully completed
- Mark tasks as 'failed' if they encounter issues

Usage Guidelines:
- Break down complex tasks into smaller, manageable steps
- Create a tasklist at the start of multi-step operations
- Keep tasklist status updated to reflect overall progress
- Mark tasklist as complete only when all tasks are done

Creating a new tasklist:
Provide title and list of tasks, marking initial tasks as running
Example: {
    "title": "Project Setup",
    "tasks": [
        {"title": "Analyze requirements", "status": "running"},
        {"title": "Create project structure", "status": "running"},
        {"title": "Implement core features"}
    ]
}

Updating task status:
Provide tasklist_id and tasks to update
Example: {
    "tasklist_id": "abc123",
    "status": "In progress...",
    "tasks": [
        {"title": "Analyze requirements", "status": "done"},
        {"title": "Create project structure", "status": "running"},
        {"title": "Implement core features", "status": "running"}
    ]
}

Task Status Values:
- ready: Task is queued but not started
- running: Task is currently in progress (REQUIRED before starting work)
- done: Task has been completed successfully
- failed: Task encountered an error or failed

This tool helps track progress and coordinate work on complex tasks. Remember:
- Always mark tasks as 'running' before starting work
- Multiple tasks can be in 'running' state
- Mark the first 1-5 tasks as 'running' when you plan to work on them soon
"""

    args_schema: type[BaseModel] = TaskListInput

    def _run(self, **kwargs) -> str:
        """Execute the task list operation."""
        try:
            input_data = TaskListInput(**kwargs)
            return asyncio.get_event_loop().run_until_complete(self._arun(input_data))
        except Exception as e:
            return f"Error managing task list: {str(e)}"

    async def _arun(self, **kwargs) -> str:
        """Async implementation of the tool."""
        try:
            input_data = TaskListInput(**kwargs)

            if input_data.tasklist_id:
                return await self._update_tasklist(input_data)
            elif input_data.title:
                return await self._create_tasklist(input_data)
            else:
                return "Either title (for creating) or tasklist_id (for updating) must be provided"

        except Exception as e:
            return f"Error managing task list: {str(e)}"

    def _format_tasklist_summary(self, tasklist: cl.TaskList, tasklist_id: str) -> str:
        """Format a summary of the tasklist's current state."""
        task_summaries = []
        for task in tasklist.tasks:
            status_str = (
                task.status.value if hasattr(task.status, "value") else str(task.status)
            )
            task_summaries.append(f"- {task.title}: {status_str}")

        tasks_str = "\n".join(task_summaries)
        return f"""Tasklist: {tasklist_id}
Status: {tasklist.status}

Tasks:
{tasks_str}"""

    async def _create_tasklist(self, input_data: TaskListInput) -> str:
        """Create a new task list."""
        # Create tasklist
        tasklist = cl.TaskList()
        tasklist.status = input_data.status

        # Create and add tasks
        for task_data in input_data.tasks:
            status = task_data.status or "ready"
            task_status = getattr(cl.TaskStatus, status.upper(), cl.TaskStatus.READY)

            task = cl.Task(title=task_data.title, status=task_status)
            await tasklist.add_task(task)

            # Link task to message if provided
            if task_data.message_id:
                task.forId = task_data.message_id

        # Store and send tasklist
        tasklist_id = str(uuid.uuid4())
        tasklist_registry[tasklist_id] = tasklist
        await tasklist.send()

        # Return creation confirmation with tasklist summary
        return {
            "created tasklist": self._format_tasklist_summary(tasklist, tasklist_id),
            "tasklist_id": tasklist_id,
        }

    async def _update_tasklist(self, input_data: TaskListInput) -> str:
        """Update an existing task list."""
        if not input_data.tasklist_id:
            return "tasklist_id is required for updates"

        tasklist = tasklist_registry.get(input_data.tasklist_id)
        if not tasklist:
            return f"No task list found with ID: {input_data.tasklist_id}"

        # Update tasklist status if provided
        if input_data.status:
            tasklist.status = input_data.status

        # Update tasks
        for task_data in input_data.tasks:
            if not task_data.status:
                continue

            # Find and update matching task
            for task in tasklist.tasks:
                if task.title == task_data.title:
                    task.status = getattr(
                        cl.TaskStatus, task_data.status.upper(), cl.TaskStatus.READY
                    )

                    # Update task message link if provided
                    if task_data.message_id:
                        task.forId = task_data.message_id

        # Update UI
        await tasklist.send()

        # Return update confirmation with current tasklist state
        return {
            "updated tasklist": self._format_tasklist_summary(
                tasklist, input_data.tasklist_id
            )
        }


def create_tasklist_tool() -> BaseTool:
    """Create and return the task list management tool."""
    return TaskListTool()
