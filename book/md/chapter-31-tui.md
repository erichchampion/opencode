# Chapter 31: The Terminal UI (TUI) — Ink, Rendering, and Interaction

---

## Notes & Key Points

### 31.1 Technology

The TUI is built with **Ink** — a React-like framework for building CLIs:
- Located in `packages/app/` (web app) and the `cli/tui/` directory
- Components rendered to the terminal
- Full keyboard navigation

### 31.2 TUI Features

- Session list with fuzzy search
- Real-time streaming of model responses
- Tool call visualization with expandable details
- Permission prompts
- Agent switching (Tab key)
- Model switching
- Session forking and management
- Markdown rendering in the terminal

### 31.3 Connection to the Engine

The TUI is just another client:
- Creates an SDK client pointing at the in-process server (or remote server)
- Subscribes to SSE events for real-time updates
- Sends prompts via the same API as the CLI

---

## Source File Map

| Concept | File |
|---------|------|
| TUI entry | `cli/tui/` directory |
| TUI routes | `server/routes/tui.ts` |
| App package | `packages/app/` |

---

## 🧪 Test References

The TUI and web app are primarily covered by **Playwright e2e specs** rather than unit tests:

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/cli/tui/thread.test.ts` | 157 | Thread/message rendering in the TUI |
| `test/cli/tui/transcript.test.ts` | 322 | Transcript export formatting |
| `test/config/tui.test.ts` | 510 | TUI configuration — keybindings, themes, scroll behavior |
| `packages/app/e2e/app/*.spec.ts` | (50 files) | Full e2e tests: navigation, palette, sessions, settings, terminal, sidebar, file operations, prompts, models |
