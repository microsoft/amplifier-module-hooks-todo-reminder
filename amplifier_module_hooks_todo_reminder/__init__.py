"""Todo reminder hook module.

Injects current todo list state into agent context before each LLM request.
Works with tool-todo to provide AI self-accountability through complex turns.
"""

import logging
from typing import Any

from amplifier_core import HookResult
from amplifier_core import ModuleCoordinator

logger = logging.getLogger(__name__)


async def mount(coordinator: ModuleCoordinator, config: dict[str, Any] | None = None):
    """Mount the todo reminder hook.

    Args:
        coordinator: Module coordinator
        config: Optional configuration
            - inject_role: Role for context injection ("user" or "system", default: "user")
            - priority: Hook priority (default: 10, runs after status context)

    Returns:
        Optional cleanup function
    """
    config = config or {}
    hook = TodoReminderHook(coordinator, config)
    hook.register(coordinator.hooks)
    logger.info("Mounted hooks-todo-reminder")
    return


class TodoReminderHook:
    """Hook that injects todo list reminders before each LLM request.

    Provides ephemeral context injection (not stored in history) to keep
    AI focused on completing all planned steps through complex multi-step turns.
    """

    def __init__(self, coordinator: ModuleCoordinator, config: dict[str, Any]):
        """Initialize todo reminder hook.

        Args:
            coordinator: Module coordinator (for accessing todo_state)
            config: Configuration dict
                - inject_role: Context injection role (default: "user")
                - priority: Hook priority (default: 10)
        """
        self.coordinator = coordinator
        self.inject_role = config.get("inject_role", "user")
        self.priority = config.get("priority", 10)

    def register(self, hooks):
        """Register hook on PROMPT_SUBMIT event."""
        # Inject at turn start (before each prompt processing)
        hooks.register("prompt:submit", self.on_prompt_submit, priority=self.priority, name="hooks-todo-reminder")

    async def on_prompt_submit(self, event: str, data: dict[str, Any]) -> HookResult:
        """Inject current todo state at start of each turn.

        Args:
            event: Event name ("prompt:submit")
            data: Event data

        Returns:
            HookResult with context injection or continue action
        """
        # Get todos from coordinator (if tool loaded and todos exist)
        todos = getattr(self.coordinator, "todo_state", None)

        logger.info(f"hooks-todo-reminder: Checking for todos, found {len(todos) if todos else 0} items")

        if not todos:
            return HookResult(action="continue")  # No todos yet

        # Format like TodoWrite display
        formatted = self._format_todos(todos)

        logger.info(f"hooks-todo-reminder: Injecting todo reminder with {len(todos)} items")

        # Inject as ephemeral context (not stored in history)
        return HookResult(
            action="inject_context",
            context_injection=f"""<current_plan>
{formatted}

Remember: Complete all pending todos before finishing this turn.
</current_plan>""",
            context_injection_role=self.inject_role,
            suppress_output=True,  # Don't show to user (ephemeral)
        )

    def _format_todos(self, todos: list[dict]) -> str:
        """Format todos like TodoWrite display.

        Args:
            todos: List of todo items

        Returns:
            Formatted string with symbols: ✓ (completed), → (in progress), ☐ (pending)
        """
        lines = []
        for todo in todos:
            status = todo["status"]
            if status == "completed":
                symbol = "✓"
            elif status == "in_progress":
                symbol = "→"
            else:  # pending
                symbol = "☐"

            # Show activeForm for in_progress, content otherwise
            text = todo["activeForm"] if status == "in_progress" else todo["content"]
            lines.append(f"{symbol} {text}")

        return "\n".join(lines)
