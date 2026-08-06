# Chapter 11: Agents -- Roles, Permissions, and Personalities

> *"An agent is a model with a job description and a set of rules."*

---

## Introduction

OpenCode ships with multiple built-in agents, each with distinct capabilities and restrictions. This chapter explains the agent system that gives the model its role.

### What You'll Learn

- The built-in agents: `build`, `plan`, `general`, `explore`, `compaction`, `title`, `summary`
- How agent permissions constrain tool access
- Custom agent creation via configuration
- The agent mode system: `primary` vs. `subagent`

---

## Notes & Key Points

### 11.1 Built-in Agents

| Agent | Mode | Description |
|-------|------|-------------|
| `build` | primary | Default full-access agent for development work |
| `plan` | primary | Read-only analysis mode, denies edit tools |
| `general` | subagent | Parallel multi-step task execution |
| `explore` | subagent | Fast read-only codebase exploration |
| `compaction` | primary (hidden) | Context window summarization |
| `title` | primary (hidden) | Session title generation |
| `summary` | primary (hidden) | Session change summarization |

### 11.2 Agent.Info Schema

Each agent is defined by:
- `name` -- identifier
- `description` -- human-readable explanation (also shown in system prompt)
- `mode` -- `"primary"` (user-facing) or `"subagent"` (invoked by other agents)
- `permission` -- ruleset controlling tool access
- `prompt` -- custom system prompt override
- `model` -- optional model override
- `temperature`, `topP` -- generation parameters
- `steps` -- max step limit
- `color` -- UI display color

### 11.3 Permission Merging

Permissions are built by merging layers:
1. Default permissions (most tools allowed)
2. Agent-specific overrides (e.g., `plan` denies `edit`)
3. User configuration overrides

```typescript
permission: PermissionNext.merge(
    defaults, agentOverrides, userOverrides)
```

### 11.4 Custom Agents

Users can define custom agents in `opencode.json`:
```json
{
  "agent": {
    "review": {
      "description": "Code review agent",
      "prompt": "You are a careful code reviewer...",
      "permission": { "edit": "deny" }
    }
  }
}
```

---

## Source File Map

| Concept | File |
|---------|------|
| Agent definitions | `agent/agent.ts` |
| Permission system | `permission/service.ts` |
| Prompt templates | `agent/prompt/*.txt` |

---

## Test References

The agent test is one of the most instructive tests in the codebase -- it systematically demonstrates every concept in this chapter:

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/agent/agent.test.ts` | 716 | **All 7 built-in agents** (build, plan, general, explore, compaction, title, summary) with correct default properties. Custom agent creation from config. Permission merging (agent-level, global-level). Agent disabling. Mode overrides. Name/prompt/steps overrides. Default agent resolution (fallback to plan when build disabled, error when all disabled). Legacy `tools` config --> permission conversion. `Truncate.GLOB` edge cases for external directory permissions. |

**Key test patterns worth highlighting:**
- `evalPerm(agent, "edit")` -- one-line permission evaluation helper
- Custom agent creation via config objects in `tmpdir()`
- Permission merge precedence: `rm -rf *` denied but `edit` still allowed
- `Agent.defaultAgent()` error paths (subagent, hidden, non-existent)

---

### 11.5 Permission Rule Evaluation Algorithm

When a tool call needs permission (e.g., `bash("rm -rf node_modules")`), the system evaluates rules in order:

```
PermissionNext.evaluate(rules, "bash", "rm -rf node_modules")
    |
    +-- 1. Filter rules to permission="bash"
    |
    +-- 2. For each matching rule, check if pattern matches:
    |       Rule { permission: "bash", pattern: "git *", action: "allow" }
    |         --> "rm -rf node_modules" matches "git *"? NO
    |       Rule { permission: "bash", pattern: "rm -rf *", action: "deny" }
    |         --> "rm -rf node_modules" matches "rm -rf *"? YES --> "deny"
    |       Rule { permission: "bash", pattern: "*", action: "ask" }
    |         --> "rm -rf node_modules" matches "*"? YES --> "ask"
    |
    +-- 3. Last matching rule wins (not first!)
    |       Both "deny" and "ask" matched, but "ask" appeared later
    |       --> Result: "ask"
    |
    |   WAIT -- why did "deny" not win?
    |   Because rules are evaluated top-to-bottom and the LAST match wins.
    |   This means more specific rules should come FIRST, with fallbacks LAST.
    |
    +-- If no rules match --> default is "ask"
```

**For bash commands, arity matters.** The `BashArity.prefix()` function extracts command prefixes for matching:
- `git checkout main` --> matches rules for `git checkout *` or `git *`
- `aws s3 ls` --> matches `aws s3 *` or `aws *`
- arity-1 commands: `ls`, `cat`, `echo` -- matched by `*`
- arity-2 commands: `git`, `docker`, `npm` -- matched by `git *`
- arity-3 commands: `aws s3`, `npm run` -- matched by `aws s3 *`

This is tested exhaustively in `test/permission/next.test.ts` (1,033 lines).

### 11.6 Agent Switching in the TUI

The TUI supports switching between agents using the **Tab key** (configurable via `tui.keybinds.switch_agent`):

1. User presses Tab --> the agent picker appears
2. Picker shows all `mode: "primary"` agents that are not `hidden`
3. User selects an agent (e.g., switches from `build` to `plan`)
4. The next prompt uses the selected agent's configuration
5. The agent change applies only to the current session -- other sessions retain their agent

**What changes when switching:**
- **Model**: each agent can specify a different model
- **Permission**: the `plan` agent denies edit/write/bash tools
- **System prompt**: the agent's custom prompt replaces the default
- **UI color**: each agent has a distinct color in the terminal

**What stays the same:**
- The session history (messages persist)
- The project context (directory, config)
- The session-level permission overrides

### 11.7 `Agent.generate()` -- AI-Generated Agents

OpenCode can generate new agent configurations using AI:

```bash
opencode generate agent
```

This launches a conversation with a meta-agent that:
1. Asks what role the new agent should fill
2. Generates a config block with name, description, prompt, model, and permissions
3. Writes it to `.opencode/agents/<name>.md` using markdown frontmatter syntax:

```markdown
---
name: Reviewer
description: Code review agent focused on correctness and style
model: anthropic/claude-sonnet-4-20250514
permission:
  bash: deny
  edit: deny
  read: allow
---

You are a careful code reviewer. Focus on:
- Logical correctness
- Edge case handling
- Code style and consistency
```

The markdown format (parsed by `config/markdown.ts`, tested in `test/config/markdown.test.ts`) allows mixing structured config with freeform prompt text.
