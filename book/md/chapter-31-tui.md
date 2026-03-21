# Chapter 31: The TUI -- Terminal User Interface

> *"The interface IS the product."*

---

## 31.1 Overview

OpenCode's TUI (`cli/cmd/tui/`) is built with Ink -- a React-like framework for terminal interfaces. It renders conversation threads, permission prompts, tool output, and status indicators in real-time using a component model.

---

## 31.2 Architecture

```
TUI Process
  |-- App component (root)
  |     |-- Chat component (main conversation view)
  |     |     |-- Thread (message rendering)
  |     |     |-- Input (user text input)
  |     |     |-- StatusBar (model, tokens, cost)
  |     |     |-- PermissionOverlay (approve/deny prompts)
  |     |
  |     |-- Sidebar (session list, optional)
  |     |-- Toast (notifications)
  |
  |-- Event subscriptions (Bus -> state updates -> re-renders)
```

The TUI subscribes to bus events for real-time updates:
- `MessageV2.Event.PartDelta` -- character-by-character text streaming
- `MessageV2.Event.PartUpdated` -- tool state transitions (pending -> running -> completed)
- `Session.Event.Updated` -- session metadata changes (title, cost)
- `Permission.Event.Asked` -- triggers the permission overlay

---

## 31.3 Thread Rendering

The `Thread` component renders messages and their parts:

- **TextPart** -- rendered as markdown-formatted terminal output
- **ToolPart** -- shows tool name, status, and collapsed/expanded output
- **ReasoningPart** -- shown in a dimmed style (chain-of-thought is secondary)
- **StepFinishPart** -- shows step number, token count, and cost
- **PatchPart** -- shows file changes with `+` green / `-` red coloring

The component uses `PartDelta` events for smooth streaming. Rather than re-rendering the entire thread on each character, it accumulates deltas in a local buffer and flushes periodically.

---

## 31.4 Input Handling

The input area supports:
- Multi-line editing (Shift+Enter for newlines)
- `@agent` mentions with autocomplete
- `@file` references with path completion
- `/command` prefixed special commands
- Ctrl-C to abort the current operation
- Up/Down arrows for prompt history

---

## 31.5 Permission Overlay

When `Permission.Event.Asked` fires, the TUI displays an overlay:

```
╭─────────────────────────────────────────────╮
│  Allow bash: npm install gray-matter ?      │
│                                             │
│  [y] Allow once  [a] Always  [n] Reject     │
╰─────────────────────────────────────────────╯
```

The overlay blocks further input until the user responds. "Always" replies are stored in the approved ruleset for the current project.

---

## 31.6 Slash Commands

Commands like `/model`, `/agent`, `/compact`, `/clear` are handled by the TUI's command parser before reaching the prompt system. They modify session state directly:

| Command | Effect |
|---------|--------|
| `/model {name}` | Switch the active model |
| `/agent {name}` | Switch the active agent |
| `/compact` | Trigger manual compaction |
| `/clear` | Clear conversation history |
| `/share` | Share the session to opencode.ai |

---

## Source File Map

| Concept | File |
|---------|------|
| TUI entry | `cli/cmd/tui/index.tsx` |
| Chat view | `cli/cmd/tui/chat.tsx` |
| Thread | `cli/cmd/tui/thread/index.tsx` |
| Input | `cli/cmd/tui/input.tsx` |
| Slash commands | `cli/cmd/tui/commands.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/cli/tui/thread.test.ts` | 157 | Thread rendering with various part types |
| `test/cli/tui/input.test.ts` | varies | Input handling, key bindings, command parsing |
