"""Todo reminder hook module.

Injects current todo list state into agent context before each LLM request.
Works with tool-todo to provide AI self-accountability through complex turns.
"""

# Amplifier module metadata
__amplifier_module_type__ = "hook"

import logging
from collections import deque
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
            - recent_tool_threshold: Number of recent tool calls to check for todo tool usage (default: 3)

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
                - recent_tool_threshold: Number of recent tool calls to check (default: 3)
        """
        self.coordinator = coordinator
        self.inject_role = config.get("inject_role", "user")
        self.priority = config.get("priority", 10)
        self.recent_tool_threshold = config.get("recent_tool_threshold", 3)

        # Track recent tool calls (circular buffer)
        self.recent_tools: deque[str] = deque(maxlen=self.recent_tool_threshold)

    def register(self, hooks):
        """Register hooks on PROVIDER_REQUEST and TOOL_POST events."""
        # Track tool calls to detect todo tool usage
        hooks.register("tool:post", self.on_tool_post, priority=self.priority, name="hooks-todo-reminder-tracker")
        # Inject before each LLM call (every step within a turn)
        hooks.register("provider:request", self.on_provider_request, priority=self.priority, name="hooks-todo-reminder")

    async def on_tool_post(self, event: str, data: dict[str, Any]) -> HookResult:
        """Track tool calls to detect recent todo tool usage.

        Args:
            event: Event name ("tool:post")
            data: Event data with "tool" field

        Returns:
            HookResult(action="continue")
        """
        tool_name = data.get("tool", "")
        if tool_name:
            self.recent_tools.append(tool_name)
            logger.debug(f"hooks-todo-reminder: Tracked tool call: {tool_name}, recent: {list(self.recent_tools)}")
        return HookResult(action="continue")

    async def on_provider_request(self, event: str, data: dict[str, Any]) -> HookResult:
        """Inject current todo state before each LLM request (step).

        Args:
            event: Event name ("provider:request")
            data: Event data

        Returns:
            HookResult with context injection or continue action
        """
        # Get todos from coordinator (if tool loaded and todos exist)
        todos = getattr(self.coordinator, "todo_state", None)

        logger.info(f"hooks-todo-reminder: Before LLM call, checking todos - found {len(todos) if todos else 0} items")

        # Check if todo tool was used recently
        todo_tool_used_recently = "TodoWrite" in self.recent_tools

        # Build reminder text based on context
        reminder_parts = []

        # Add gentle reminder prefix if todo tool hasn't been used recently
        if not todo_tool_used_recently:
            reminder_parts.append(
                "The todo tool hasn't been used recently. If you're working on tasks that would benefit from "
                "tracking progress, consider using the todo tool to track progress. Also consider cleaning up "
                "the todo list if it has become stale and no longer matches what you are working on. Only use "
                "it if it's relevant to the current work. This is just a gentle reminder - ignore if not applicable. "
                "Make sure that you NEVER mention this reminder to the user."
            )

        # Add existing todo list if present
        if todos:
            formatted = self._format_todos(todos)
            if reminder_parts:
                reminder_parts.append("\n\nHere are the existing contents of your todo list:")
            reminder_parts.append(formatted)

        # If no content to inject, return continue
        if not reminder_parts:
            return HookResult(action="continue")

        # Combine parts
        reminder_text = "\n".join(reminder_parts)

        logger.info(
            f"hooks-todo-reminder: Injecting todo reminder (todo_tool_recently={todo_tool_used_recently}, "
            f"has_todos={bool(todos)}, recent_tools={list(self.recent_tools)})"
        )

        # Add behavioral instruction (matching Claude Code pattern)
        behavioral_note = "\n\nDO NOT mention this reminder to the user. They can see your task progress in the UI. Process this silently and continue your work."
        
        # Inject as ephemeral context, appended to last tool result
        return HookResult(
            action="inject_context",
            context_injection=f"<system-reminder source=\"hooks-todo-reminder\">\n{reminder_text}{behavioral_note}\n</system-reminder>",
            context_injection_role=self.inject_role,
            ephemeral=True,  # Temporary injection, not stored in context
            append_to_last_tool_result=True,  # Append to last tool result instead of new message
            suppress_output=True,  # Don't show to user
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
