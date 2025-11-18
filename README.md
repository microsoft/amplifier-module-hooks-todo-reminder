# amplifier-module-hooks-todo-reminder

Hook that injects todo list reminders into AI context before each LLM request.

## Purpose

Automatically injects current todo state into AI's context before each LLM request (step), providing gentle, contextual reminders that help AI track progress without being overly prescriptive.

Works with `amplifier-module-tool-todo` to create an AI accountability loop with adaptive guidance based on recent tool usage.

## How It Works

1. **Tracks tool usage** via `tool:post` events to detect recent todo tool usage
2. **Hook triggers** on `provider:request` event (before each LLM call)
3. **Checks** for `coordinator.todo_state` (populated by tool-todo)
4. **Generates adaptive reminder**:
   - If todo tool not used recently (last 3 tools): Gentle reminder to consider using it
   - If todos exist: Shows current todo list with ✓/→/☐ symbols
5. **Appends to last tool result** (if applicable) or creates new message as fallback
6. **AI sees** contextual reminder attached to tool output

**Key insight:** By appending to the last tool result instead of creating a separate message, the reminder feels less intrusive and more contextual. The adaptive messaging prevents over-compliance while maintaining awareness.

## Installation

```bash
uv add amplifier-module-hooks-todo-reminder
```

## Configuration

Add to your profile:

```yaml
hooks:
  - module: hooks-todo-reminder
    source: git+https://github.com/microsoft/amplifier-module-hooks-todo-reminder@main
    config:
      inject_role: user # Role for injection (default: "user")
      priority: 10 # Hook priority (default: 10)
      recent_tool_threshold: 3 # Number of recent tools to check (default: 3)
```

### Configuration Options

- **inject_role** (default: "user")

  - Context injection role
  - Options: "user" | "system" | "assistant"
  - Recommended: "user" (tested to work correctly)

- **priority** (default: 10)

  - Hook execution priority
  - Higher numbers run after lower numbers
  - Recommended: 10 (runs after status context at priority 0)

- **recent_tool_threshold** (default: 3)
  - Number of recent tool calls to check for todo tool usage
  - If todo tool not found in last N calls, shows gentle reminder
  - Lower value = more frequent reminders, higher value = less frequent

## Injection Format

The hook appends a contextual reminder to the last tool result (or creates a new message if last message isn't a tool result).

**When todo tool hasn't been used recently:**

```xml
<system-reminder>
The todo tool hasn't been used recently. If you're working on tasks that would benefit from
tracking progress, consider using the todo tool to track progress. Also consider cleaning up
the todo list if it has become stale and no longer matches what you are working on. Only use
it if it's relevant to the current work. This is just a gentle reminder - ignore if not applicable.
Make sure that you NEVER mention this reminder to the user.

Here are the existing contents of your todo list:
✓ Completed task
→ In-progress task
☐ Pending task
</system-reminder>
```

**When todo tool was used recently:**

```xml
<system-reminder>
✓ Completed task
→ In-progress task
☐ Pending task
</system-reminder>
```

**Symbols:**

- ✓ = completed
- → = in_progress (shows activeForm instead of content)
- ☐ = pending

**Placement:** Appended to the last tool result message for contextual awareness, falls back to new message if needed.

## Example: Multi-Step Accountability Within Single Turn

### Turn 1: AI creates plan

```
User: "Implement feature X with tests"
AI: [Creates 3-step plan using tool-todo]
  1. Implement code (pending)
  2. Write tests (pending)
  3. Verify tests pass (pending)
```

### Turn 2: AI executes all steps, maintaining awareness

```
[User submits prompt: "Do it"]

Step 1 (LLM call before first action):
  [provider:request fires]
  [Last message: user prompt "Do it"]
  Hook: No tool result to append to → Creates new message
  Hook injects:
    <system-reminder>
    ☐ Implement code
    ☐ Write tests
    ☐ Verify tests pass
    </system-reminder>

  AI: [Sees full plan, decides to implement code first]
  → Calls Write tool, marks "Implement code" as in_progress

Step 2 (LLM call after tool execution):
  [provider:request fires again]
  [Last message: tool result from Write]
  Hook: Appends to Write tool result
  Tool result now includes:
    ...original Write output...

    <system-reminder>
    ✓ Implement code
    ☐ Write tests
    ☐ Verify tests pass
    </system-reminder>

  AI: [Sees updated plan attached to what just happened, knows what's next]
  → Calls Write tool for tests, marks "Write tests" as in_progress

Step 3 (LLM call after second tool):
  [provider:request fires again]
  [Last message: tool result from Write (tests)]
  Hook: Appends to tool result
  Tool result includes:
    ...test file written...

    <system-reminder>
    The todo tool hasn't been used recently. If you're working on tasks that would
    benefit from tracking progress, consider using the todo tool to track progress.
    [...]

    Here are the existing contents of your todo list:
    ✓ Implement code
    ✓ Write tests
    ☐ Verify tests pass
    </system-reminder>

  AI: [Sees gentle reminder + progress, one task remaining]
  → Calls Bash tool to run tests, marks "Verify" as in_progress

Step 4 (LLM call after third tool):
  [provider:request fires again]
  [Last message: tool result from Bash (test output)]
  Hook: Appends to Bash tool result
  Tool result includes:
    ...test output: all passed...

    <system-reminder>
    ✓ Implement code
    ✓ Write tests
    ✓ Verify tests pass
    </system-reminder>

  AI: [Sees all complete contextually with test results, provides summary]
  → Final response to user
```

**Notice:**
- Single turn, but hook fires 4 times (before each LLM call)
- Reminder appended to tool results for contextual awareness
- Gentle reminder appears when todo tool not used recently
- AI never loses track of the plan, but isn't overly rigid about it

## Key Features

### Adaptive Messaging

The hook adapts its messaging based on recent tool usage:

- **Todo tool used recently**: Shows only the current todo list (concise)
- **Todo tool not used recently**: Adds gentle reminder suggesting todo tool usage (helpful but not pushy)
- **No todos**: Returns continue (silent until todos exist)

### Contextual Placement

Reminders are appended to tool results for natural context flow:

- ✅ Feels less intrusive than separate messages
- ✅ Reminder appears right after the relevant action
- ✅ Falls back to new message if last message isn't a tool result

### Ephemeral Injection

Context injection is **not stored** in conversation history. It's injected fresh before each LLM request, so:

- ✅ No context pollution from old states
- ✅ Only latest plan visible
- ✅ Automatic cleanup (nothing to persist)

### Session-Scoped

Todos live only during the current session:

- Created when AI calls tool-todo
- Injected by hook before each LLM call
- Cleared when session ends

### Graceful Degradation

- If tool-todo not loaded → hook returns `continue` (no-op)
- If no todos created yet → hook returns `continue`
- Hook failures don't crash session (non-interference)

## Integration with tool-todo

This hook is designed to work seamlessly with `amplifier-module-tool-todo`:

```
tool-todo (storage)  +  hooks-todo-reminder (injection)  =  AI accountability
```

**Without reminder hook:**

- AI calls tool-todo ✓
- Tool stores todos ✓
- AI must manually check status ✗
- Risk: AI forgets to check during multi-step execution ✗

**With reminder hook:**

- AI calls tool-todo ✓
- Tool stores todos ✓
- Hook auto-injects before every LLM call ✓
- AI sees status at every decision point ✓
- AI maintains awareness through complex turns ✓

## Philosophy Alignment

- ✅ **Mechanism not policy**: Hook provides injection mechanism, AI decides how to use todos
- ✅ **Ruthless simplicity**: Hooks one event, formats, injects - that's it
- ✅ **Separation of concerns**: Hook doesn't manage todos, just injects them
- ✅ **Non-interference**: Failures return continue, never crash
- ✅ **Observability**: Logs injection activity for debugging

## Implementation Details

### Hook Registration

Registers on `provider:request` event (before each LLM call):

```python
hooks.register("provider:request", self.on_provider_request, priority=10, name="hooks-todo-reminder")
```

### Injection Logic

1. Check `coordinator.todo_state`
2. If empty → return `HookResult(action="continue")`
3. If present → format and inject:

```python
HookResult(
    action="inject_context",
    context_injection="<system-reminder>...</system-reminder>",
    context_injection_role="user",
    suppress_output=True
)
```

### Format Details

- **Completed**: ✓ + content
- **In progress**: → + activeForm (present continuous)
- **Pending**: ☐ + content

Matches TodoWrite display format for consistency.

## Testing

Integration tests verify:

```bash
# Basic integration
python test_todo_integration.py

# Multi-step accountability
python test_todo_multi_step.py
```

Tests confirm:

- Hook triggers on provider:request
- Injection contains formatted todo list
- Multiple injections during single turn
- Context receives messages at each step
- Format matches spec (✓/→/☐)

## Contributing

> [!NOTE]
> This project is not currently accepting external contributions, but we're actively working toward opening this up. We value community input and look forward to collaborating in the future. For now, feel free to fork and experiment!

Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit [Contributor License Agreements](https://cla.opensource.microsoft.com).

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft
trademarks or logos is subject to and must follow
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
