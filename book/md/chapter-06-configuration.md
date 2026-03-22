# Chapter 6: Configuration -- Loading, Merging, and Validating Settings

> *"Configuration is the contract between the developer and the tool."*

---

## Introduction

OpenCode's configuration system supports multiple sources (global config, project config, environment variables) with a well-defined merge order. This chapter explains how configuration is loaded, validated, and used throughout the system.

### What You'll Learn

- Configuration file locations and formats (`opencode.json`, `.opencode/config.json`)
- The Zod-based config schema
- Merge order: defaults --> global --> project --> environment --> CLI flags
- How `Config.get()` caches and provides configuration
- Configuration hot-reloading

---

## Notes & Key Points

### 6.1 Config File

The primary config file is `opencode.json` (or `.opencode/config.json`). The file is a massive 56KB Zod schema in `config/config.ts` covering:

- Provider configuration (API keys, base URLs, models)
- Agent configuration (custom agents, permissions, prompts)
- Default model and agent
- Experimental features
- Sharing settings
- Permission defaults
- MCP server definitions

### 6.2 Configuration Paths

Managed by `config/paths.ts`:
- Global config: `~/.config/opencode/` (XDG-compliant)
- Project config: `.opencode/` in the project root
- State data: `~/.local/share/opencode/` or `~/Library/Application Support/opencode/`

### 6.3 Config Directories for Custom Tools/Skills

`Config.directories()` returns an array of directories to search for custom tools, skills, and other extensions:
- `.opencode/` in the project root
- Global config directory

### 6.4 The `Config.get()` Pattern

Returns the merged, validated configuration. Uses `Instance.state()` for caching -- computed once per instance.

---

## Source File Map

| Concept | File |
|---------|------|
| Config schema | `config/config.ts` |
| Config paths | `config/paths.ts` |
| Markdown config | `config/markdown.ts` |
| TUI config | `config/tui.ts` |

---

## Test References

Configuration has the most extensive test coverage in the project:

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/config/config.test.ts` | 2,078 | Config loading (JSON/JSONC), merging multiple files with precedence, env var substitution (`{env:VAR}`), file inclusion (`{file:path}`), schema validation, agent/command configuration from `.opencode/` directories, managed settings, dependency installation serialization, Windows path handling, migration of legacy fields (`autoshare` --> `share`, `mode` --> `agent`) |
| `test/config/markdown.test.ts` | 228 | Front matter parsing for markdown-based agent/command definitions, edge cases (empty frontmatter, no frontmatter, weird model IDs) |
| `test/config/tui.test.ts` | 510 | TUI-specific key bindings, theme configuration, scroll settings |
| `test/config/agent-color.test.ts` | 71 | Agent color assignment and cycling |

---

### 6.5 Configuration Examples

**Minimal `opencode.json`** -- just set a provider and model:

```jsonc
{
  "provider": {
    "anthropic": {
      "api_key": "{env:ANTHROPIC_API_KEY}"
    }
  },
  "model": "anthropic/claude-sonnet-4-20250514"
}
```

**Full `opencode.json`** -- demonstrating most available options:

```jsonc
{
  // Default model for all agents
  "model": "anthropic/claude-sonnet-4-20250514",

  // Provider configuration
  "provider": {
    "anthropic": {
      "api_key": "{env:ANTHROPIC_API_KEY}"
    },
    "openai": {
      "api_key": "{file:~/.openai-key}",
      "models": {
        "gpt-4o": {
          "max_tokens": 8192,
          "temperature": 0.7
        }
      }
    }
  },

  // Agent configuration
  "agent": {
    "build": {
      "model": "anthropic/claude-sonnet-4-20250514",
      "permission": {
        "bash": { "git *": "allow", "rm -rf *": "deny", "*": "ask" },
        "edit": "allow",
        "read": "allow"
      }
    },
    "custom-reviewer": {
      "name": "Reviewer",
      "model": "openai/gpt-4o",
      "prompt": "You are a code reviewer. Focus on correctness and style.",
      "permission": {
        "bash": "deny",
        "edit": "deny",
        "read": "allow"
      }
    }
  },

  // MCP servers
  "mcp": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
    }
  },

  // Permission defaults (applied to all agents unless overridden)
  "permission": {
    "bash": { "*": "ask" },
    "edit": "allow"
  },

  // Sharing
  "share": true
}
```

Note the `{env:VARIABLE}` and `{file:path}` substitution syntax -- values are resolved at config load time. This allows secrets to stay out of checked-in config files.

### 6.6 Environment Variable Overrides

OpenCode supports several environment variable patterns:

| Pattern | Purpose | Example |
|---------|---------|---------|
| `OPENCODE_MODEL` | Override the default model | `OPENCODE_MODEL=openai/gpt-4o` |
| `OPENCODE_PROVIDER_<NAME>_API_KEY` | Set a provider API key | `OPENCODE_PROVIDER_ANTHROPIC_API_KEY=sk-...` |
| `OPENCODE_FLAG_<NAME>` | Enable/disable feature flags | `OPENCODE_FLAG_STREAMING=true` |
| `OPENCODE_SERVER_PASSWORD` | Enable basic auth on the HTTP server | `OPENCODE_SERVER_PASSWORD=secret` |
| `OPENCODE_DIR` | Override project directory detection | `OPENCODE_DIR=/my/project` |
| `AGENT=1` | Set by OpenCode itself -- indicates running inside an agent | Auto-set |
| `OPENCODE=1` | Set by OpenCode -- indicates the process is OpenCode | Auto-set |

Environment variables take precedence over config file values. The merge order is:

```
defaults --> global config --> project config --> environment variables --> CLI flags
```

### 6.7 TUI-Specific Configuration

The TUI section of the config (`config/tui.ts`) controls the terminal interface appearance and behavior:

```jsonc
{
  "tui": {
    "theme": "dark",
    "keybinds": {
      "submit": "enter",
      "cancel": "escape",
      "switch_agent": "tab"
    },
    "scroll": {
      "speed": 3,
      "page_size": 20
    }
  }
}
```

Key configurable aspects:
- **Theme**: color scheme for the terminal UI
- **Key bindings**: customizable shortcuts for all major actions (submit, cancel, switch agent, open file, etc.)
- **Scroll behavior**: scroll speed and page size for message viewing
- **Agent colors**: each agent gets a distinct color for visual identification in the TUI

The `test/config/tui.test.ts` (510 lines) covers all these options extensively.
