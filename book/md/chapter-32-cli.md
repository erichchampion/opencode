# Chapter 32: The CLI -- Commands and Non-Interactive Mode

> *"Not everything needs a TUI."*

---

## 32.1 Overview

OpenCode's CLI (`cli/cmd/`) provides both interactive (TUI) and non-interactive modes. The CLI is built with a command framework that handles argument parsing, help generation, and subcommand routing.

---

## 32.2 Command Structure

```
opencode                    # Launch TUI (default)
opencode "prompt text"      # Non-interactive: send prompt, print response, exit
opencode -p "prompt"        # Same as above
opencode config             # Show configuration
opencode mcp status         # Show MCP server status
opencode mcp auth {name}    # Start OAuth flow for an MCP server
```

### Non-Interactive Mode

When a prompt is passed as an argument, OpenCode runs in "headless" mode:

1. Creates a new session (or uses `--session {id}`)
2. Sends the prompt via `SessionPrompt.prompt()`
3. Streams the response to stdout (markdown formatted)
4. Exits with code 0 on success, non-zero on error

This enables scripting and CI/CD integration:

```bash
result=$(opencode "What does the main function do in app.ts?")
echo "$result"
```

---

## 32.3 Output Modes

| Flag | Format | Use Case |
|------|--------|----------|
| (default) | Markdown with ANSI colors | Human reading |
| `--json` | JSON lines | Script consumption |
| `--quiet` | Minimal output | CI/CD |

---

## 32.4 Environment Variables

| Variable | Purpose |
|----------|---------|
| `OPENCODE_CONFIG_DIR` | Custom config directory |
| `OPENCODE_DISABLE_PROJECT_CONFIG` | Skip project-level config |
| `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT` | Skip `CLAUDE.md` loading |
| `OPENCODE_AUTO_SHARE` | Auto-share all sessions |
| `OPENCODE_CLIENT` | Client identifier for telemetry |

---

## Source File Map

| Concept | File |
|---------|------|
| CLI entry | `cli/cmd/index.ts` |
| Config command | `cli/cmd/config.ts` |
| MCP commands | `cli/cmd/mcp.ts` |
