# Chapter 31: The TUI -- Terminal User Interface

> *"The interface IS the product."*

---

## 31.1 Overview

OpenCode's TUI (`cli/cmd/tui/`) is built with Ink -- a React-like framework for terminal interfaces. It renders conversation threads, permission prompts, tool output, and status indicators in real-time using a component model.

---

## 31.2 Ink: React for the Terminal

Ink uses React's component model to render terminal output. Components are functions that return JSX, state is managed with hooks (`useState`, `useEffect`), and re-renders are triggered by state changes -- just like a web React app, but rendered to the terminal instead of the DOM.

```typescript
// Simplified TUI component pattern
function StatusBar() {
  const [session, setSession] = useState<Session.Info>()
  
  useEffect(() => {
    return Bus.subscribe(Session.Event.Updated, (event) => {
      setSession(event.properties.info)
    })
  }, [])
  
  return <Box>
    <Text color="cyan">{session?.model}</Text>
    <Text> | </Text>
    <Text color="green">${session?.cost.toFixed(4)}</Text>
  </Box>
}
```

This is why Bus events drive the TUI: each event triggers a `setState`, which triggers a re-render of the affected component.

---

## 31.3 Architecture

```
TUI Process
  |-- App component (root)
  |     |-- Chat component (main conversation view)
  |     |     |-- Thread (message rendering)
  |     |     |-- Input (user text input)
  |     |     |-- StatusBar (model, agent, tokens, cost)
  |     |     |-- PermissionOverlay (approve/deny prompts)
  |     |     |-- TodoPanel (task list from todowrite)
  |     |
  |     |-- Sidebar (session list, history)
  |     |-- Toast (notifications)
  |
  |-- Event subscriptions (Bus --> state updates --> re-renders)
```

---

## 31.4 Thread Rendering

The `Thread` component renders messages and their parts:

- **TextPart** -- rendered as markdown-formatted terminal output
- **ToolPart** -- shows tool name, status icon, and collapsed/expanded output
- **ReasoningPart** -- shown in a dimmed style (chain-of-thought is secondary)
- **StepFinishPart** -- shows step number, token count, and cost
- **PatchPart** -- shows file changes with `+` green / `-` red coloring

The component uses `PartDelta` events for smooth streaming. Rather than re-rendering the entire thread on each character, it accumulates deltas in a local buffer and flushes periodically.

---

## 31.5 Input Handling

The input area supports:
- Multi-line editing (Shift+Enter for newlines)
- `@agent` mentions with autocomplete
- `@file` references with path completion
- `/command` prefixed special commands
- Up/Down arrows for prompt history
- Paste from clipboard

---

## 31.6 Keyboard Shortcuts

| Key | Context | Action |
|-----|---------|--------|
| `Enter` | Input | Send prompt |
| `Shift+Enter` | Input | New line |
| `Ctrl+C` | Any | Abort current operation / Exit |
| `Up` / `Down` | Input (empty) | Browse prompt history |
| `Tab` | Input | Switch between agents (build <--> plan) |
| `Escape` | Any | Cancel current action, close overlay |
| `y` | Permission overlay | Allow once |
| `a` | Permission overlay | Always allow (for this session) |
| `n` | Permission overlay | Reject |
| `/` | Input (start) | Begin slash command |

---

## 31.7 Permission Overlay

When `Permission.Event.Asked` fires, the TUI displays an overlay:

```
+---------------------------------------------+
|  Allow bash: npm install gray-matter ?      |
|                                             |
|  [y] Allow once  [a] Always  [n] Reject     |
+---------------------------------------------+
```

The overlay blocks further input until the user responds. "Always" replies are stored in the approved ruleset for the current project.

---

## 31.8 Slash Commands

Commands like `/model`, `/agent`, `/compact`, `/clear` are handled by the TUI's command parser before reaching the prompt system. They modify session state directly:

| Command | Effect |
|---------|--------|
| `/model {name}` | Switch the active model |
| `/agent {name}` | Switch the active agent |
| `/compact` | Trigger manual compaction |
| `/clear` | Clear conversation history |
| `/share` | Share the session to opencode.ai |
| `/bug` | Report a bug with session context |
| `/cost` | Show session cost breakdown |

---

## 31.9 Status Bar

The status bar at the bottom of the TUI shows:
- **Model name** -- currently active model (e.g., `claude-sonnet-4-20250514`)
- **Agent name** -- active agent with color indicator (e.g., `build`, `plan`)
- **Token count** -- input/output tokens for the current step
- **Cost** -- cumulative session cost in USD
- **Latency** -- time for the current/last response

---

## 31.10 Theme Configuration

TUI colors and key bindings are configurable in `opencode.json`:

```json
{
  "tui": {
    "theme": "dark",
    "agent_colors": {
      "build": "#4CAF50",
      "plan": "#2196F3"
    }
  }
}
```

Each agent gets a distinct color for visual identification. Theme options are tested in `test/config/tui.test.ts` (510 lines).

---

## Source File Map

| Concept | File |
|---------|------|
| TUI entry | `cli/cmd/tui/index.tsx` |
| Chat view | `cli/cmd/tui/chat.tsx` |
| Thread | `cli/cmd/tui/thread/index.tsx` |
| Input | `cli/cmd/tui/input.tsx` |
| Slash commands | `cli/cmd/tui/commands.ts` |
| TUI events | `cli/cmd/tui/event.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/cli/tui/thread.test.ts` | 157 | Thread rendering with various part types |
| `test/cli/tui/input.test.ts` | varies | Input handling, key bindings, command parsing |
| `test/config/tui.test.ts` | 510 | TUI-specific key bindings, theme configuration |
