# Chapter 32: The CLI -- Commands and Non-Interactive Mode

> *"Not everything needs a TUI."*

---

## 32.1 Overview

OpenCode's CLI (`cli/cmd/`) provides both interactive (TUI) and non-interactive modes. 22 commands are registered via yargs, covering interactive use, headless prompts, server management, and administrative tasks.

---

## 32.2 Full Command Reference

```
opencode                         # Launch TUI (default)
opencode "prompt text"           # Non-interactive: send prompt, print response, exit
opencode -p "prompt"             # Same as above (explicit flag)
```

### Session Commands

| Command | Purpose |
|---------|---------|
| `opencode` | Launch TUI (default command) |
| `opencode "prompt"` / `-p "prompt"` | Send a one-shot prompt, stream response, exit |
| `opencode session list` | List all sessions |
| `opencode session export {id}` | Export a session's messages |

### Configuration & Auth

| Command | Purpose |
|---------|---------|
| `opencode config` | Show current configuration |
| `opencode auth login {provider}` | Start OAuth or API key setup |
| `opencode auth logout {provider}` | Remove stored credentials |
| `opencode auth status` | Show auth status for all providers |
| `opencode providers` | List available providers and models |
| `opencode models` | List available models |

### Server & Development

| Command | Purpose |
|---------|---------|
| `opencode serve` | Start the HTTP server only (no TUI) |
| `opencode web` | Open web UI |
| `opencode debug` | Show debug information |
| `opencode stats` | Show usage statistics |

### MCP & Plugins

| Command | Purpose |
|---------|---------|
| `opencode mcp status` | Show MCP server connection status |
| `opencode mcp auth {name}` | Start OAuth flow for an MCP server |

### Administration

| Command | Purpose |
|---------|---------|
| `opencode upgrade` | Upgrade to latest version |
| `opencode uninstall` | Remove OpenCode from the system |
| `opencode export` | Export data |
| `opencode import` | Import data |
| `opencode agent` | Agent management |
| `opencode acp` | Auto-commit and push |
| `opencode pr` | Pull request operations |
| `opencode github` | GitHub integration |

---

## 32.3 Non-Interactive Mode

When a prompt is passed as an argument, OpenCode runs in "headless" mode:

1. Creates a new session (or uses `--session {id}` to resume)
2. Sends the prompt via `SessionPrompt.prompt()`
3. Streams the response to stdout (markdown formatted)
4. Exits with code 0 on success, non-zero on error

### Per-Invocation Flags

| Flag | Purpose |
|------|---------|
| `--session {id}` | Resume an existing session |
| `--model {name}` | Override the default model |
| `--agent {name}` | Use a specific agent |
| `--json` | Output as JSON lines |
| `--quiet` | Minimal output |

---

## 32.4 Pipe Mode

OpenCode can read prompts from stdin:

```bash
echo "Explain this function" | opencode
cat README.md | opencode "Summarize this file"
```

This enables integration with other tools and scripts.

---

## 32.5 Output Modes

| Flag | Format | Use Case |
|------|--------|----------|
| (default) | Markdown with ANSI colors | Human reading |
| `--json` | JSON lines | Script consumption |
| `--quiet` | Minimal output | CI/CD |

---

## 32.6 Scripting Examples

**Code review in CI/CD:**

```bash
git diff HEAD~1 | opencode "Review these changes for bugs" --quiet
```

**Batch file analysis:**

```bash
for f in src/*.ts; do
  opencode "Summarize what $f does" --quiet >> analysis.md
done
```

**Session continuation:**

```bash
# Start a session
SESSION=$(opencode "Set up a React project" --json | jq -r '.sessionID')

# Continue in the same session
opencode --session "$SESSION" "Add a login form"
opencode --session "$SESSION" "Add unit tests"
```

---

## 32.7 Environment Variables

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
| CLI entry & yargs setup | `src/index.ts` |
| TUI command | `cli/cmd/tui/index.tsx` |
| Run (headless) command | `cli/cmd/run.ts` |
| Config command | `cli/cmd/config.ts` |
| MCP commands | `cli/cmd/mcp.ts` |
| Auth commands | `cli/cmd/auth.ts` |
| Serve command | `cli/cmd/serve.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/cli/github-action.test.ts` | 198 | GitHub Action integration for non-interactive mode |
| `test/cli/import.test.ts` | 54 | Session import/export roundtrip |
| `test/cli/github-remote.test.ts` | 80 | GitHub remote detection and PR operations |


