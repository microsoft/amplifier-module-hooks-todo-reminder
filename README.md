# amplifier-module-hooks-todo-reminder

Hook that injects todo list reminders into AI context before each turn.

## Purpose

Automatically injects current todo state into AI's context at the start of each turn, providing ephemeral reminders that keep AI focused on completing all planned steps.

Works with `amplifier-module-tool-todo` to create an AI accountability loop.

## How It Works

1. **Hook triggers** on `prompt:submit` event (start of each turn)
2. **Checks** for `coordinator.todo_state` (populated by tool-todo)
3. **Formats** todos like TodoWrite display (✓/→/☐ symbols)
4. **Injects** as ephemeral context (not stored in history)
5. **AI sees** reminder before generating response

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

## Injection Format

The hook injects a formatted reminder showing current plan state:

```xml
<current_plan>
✓ Completed task
→ In-progress task
☐ Pending task
☐ Another pending task

Remember: Complete all pending todos before finishing this turn.
</current_plan>
```

**Symbols:**

- ✓ = completed
- → = in_progress (shows activeForm instead of content)
- ☐ = pending

## Example: Multi-Turn Accountability

### Turn 1: AI creates plan

```
User: "Implement feature X"
AI: [Creates 5-step plan using tool-todo]
  1. Research requirements (pending)
  2. Design solution (pending)
  3. Implement code (pending)
  4. Write tests (pending)
  5. Document changes (pending)
```

### Turn 2: AI starts work, sees reminder

```
[prompt:submit fires]
Hook injects:
  <current_plan>
  ☐ Research requirements
  ☐ Design solution
  ☐ Implement code
  ☐ Write tests
  ☐ Document changes
  Remember: Complete all pending todos before finishing this turn.
  </current_plan>

AI: [Sees reminder, works on step 1, marks it completed]
```

### Turn 3: AI sees progress

```
[prompt:submit fires]
Hook injects:
  <current_plan>
  ✓ Research requirements
  ☐ Design solution
  ☐ Implement code
  ☐ Write tests
  ☐ Document changes
  Remember: Complete all pending todos before finishing this turn.
  </current_plan>

AI: [Sees 4 steps remaining, continues to step 2]
```

## Key Features

### Ephemeral Injection

Context injection is **not stored** in conversation history. It's injected fresh each turn, so:

- ✅ No context pollution from old states
- ✅ Only latest plan visible
- ✅ Automatic cleanup (nothing to persist)

### Session-Scoped

Todos live only during the current session:

- Created when AI calls tool-todo
- Injected by hook each turn
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
- Risk: AI forgets to check, loses focus ✗

**With reminder hook:**

- AI calls tool-todo ✓
- Tool stores todos ✓
- Hook auto-injects reminders ✓
- AI sees status every turn ✓
- AI stays focused ✓

## Philosophy Alignment

- ✅ **Mechanism not policy**: Hook provides injection mechanism, AI decides how to use todos
- ✅ **Ruthless simplicity**: Hooks one event, formats, injects - that's it
- ✅ **Separation of concerns**: Hook doesn't manage todos, just injects them
- ✅ **Non-interference**: Failures return continue, never crash
- ✅ **Observability**: Logs injection activity for debugging

## Implementation Details

### Hook Registration

Registers on `prompt:submit` event (start of each turn):

```python
hooks.register("prompt:submit", self.on_prompt_submit, priority=10, name="hooks-todo-reminder")
```

### Injection Logic

1. Check `coordinator.todo_state`
2. If empty → return `HookResult(action="continue")`
3. If present → format and inject:

```python
HookResult(
    action="inject_context",
    context_injection="<current_plan>...</current_plan>",
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

# Multi-turn accountability
python test_todo_multi_turn.py
```

Tests confirm:

- Hook triggers on prompt:submit
- Injection contains formatted todo list
- Context receives messages
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
