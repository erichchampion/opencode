# Chapter 15: The System Prompt -- Identity, Context, and Instructions

> *"You are a powerful AI coding assistant..."*

---

## 15.1 What the Model Sees First

Before the model receives any user messages, it gets a system prompt that defines its identity, capabilities, and constraints. This prompt is assembled from multiple sources and can be several thousand tokens long. Understanding its structure is key to understanding the model's behavior.

The system prompt assembly happens in two places:
- `SystemPrompt` (`session/system.ts`) -- provider-specific identity prompts and environment context
- `InstructionPrompt` (`session/instruction.ts`) -- user-defined instructions from files and config

---

## 15.2 Provider-Specific Identity

`SystemPrompt.provider()` selects a base identity prompt based on the model:

```typescript
export function provider(model: Provider.Model) {
  if (model.api.id.includes("gpt-4") || model.api.id.includes("o1") || model.api.id.includes("o3"))
    return [PROMPT_BEAST]
  if (model.api.id.includes("gpt")) return [PROMPT_CODEX]
  if (model.api.id.includes("gemini-")) return [PROMPT_GEMINI]
  if (model.api.id.includes("claude")) return [PROMPT_ANTHROPIC]
  if (model.api.id.toLowerCase().includes("trinity")) return [PROMPT_TRINITY]
  return [PROMPT_DEFAULT]
}
```

Each prompt file (imported as text from `session/prompt/*.txt`) is tailored for the model family's strengths. For example, the Anthropic prompt may emphasize artifact creation, while the OpenAI prompt may focus on structured tool use. The `PROMPT_DEFAULT` covers generic models and LiteLLM proxies.

If the active agent has a custom `prompt` field, it replaces the provider prompt entirely. This is how agents like `plan` get different personalities.

---

## 15.3 Environment Context

`SystemPrompt.environment()` injects runtime information:

```typescript
export async function environment(model: Provider.Model) {
  return [`
    You are powered by the model named ${model.api.id}.
    <env>
      Working directory: ${Instance.directory}
      Workspace root folder: ${Instance.worktree}
      Is directory a git repo: ${project.vcs === "git" ? "yes" : "no"}
      Platform: ${process.platform}
      Today's date: ${new Date().toDateString()}
    </env>
  `]
}
```

This tells the model where it's operating, what tools are available (git or not), and the current date. The XML-like `<env>` tags help the model identify structured context from prose.

---

## 15.4 Instruction Files -- AGENTS.md and Friends

`InstructionPrompt.system()` loads user-defined instructions from multiple sources, in priority order:

1. **Project-level** -- searches up from the working directory for:
   - `AGENTS.md` (OpenCode's native format)
   - `CLAUDE.md` (compatibility with Claude Code)
   - `CONTEXT.md` (deprecated)
2. **Global-level** -- loads from:
   - `$OPENCODE_CONFIG_DIR/AGENTS.md`
   - `~/.opencode/AGENTS.md`
   - `~/.claude/CLAUDE.md` (unless `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT`)
3. **Config-specified** -- entries in the `instructions` array in `opencode.json`:
   - File paths (relative or absolute, with glob support)
   - URLs (fetched with a 5-second timeout)

Each instruction is prefixed with `"Instructions from: {path}"` so the model knows where it came from. This is useful when debugging unexpected model behavior -- you can check which instruction files are active.

---

## 15.5 Directory-Scoped Instructions

`InstructionPrompt.resolve()` handles a powerful feature: instruction files that are scoped to specific directories. When the `ReadTool` reads a file, it triggers instruction resolution:

```typescript
export async function resolve(messages, filepath, messageID) {
  // Walk from filepath's directory up to the project root
  let current = path.dirname(target)
  while (current.startsWith(root) && current !== root) {
    const found = await find(current)  // looks for AGENTS.md, CLAUDE.md
    if (found && !system.has(found) && !already.has(found) && !isClaimed(messageID, found)) {
      claim(messageID, found)  // prevent duplicate loading
      results.push({ filepath: found, content: "Instructions from: " + found + "\n" + content })
    }
    current = path.dirname(current)
  }
}
```

This means a subdirectory can have its own `AGENTS.md` with instructions specific to that component. When the model reads files in that directory, it automatically picks up the local instructions.

The `claim()` mechanism prevents the same instruction file from being loaded multiple times within the same message turn.

---

## 15.6 Skill Prompts

`SystemPrompt.skills()` loads skill descriptions for the model:

```typescript
export async function skills(agent: Agent.Info) {
  if (PermissionNext.disabled(["skill"], agent.permission).has("skill")) return
  const list = await Skill.available(agent)
  return [
    "Skills provide specialized instructions and workflows for specific tasks.",
    "Use the skill tool to load a skill when a task matches its description.",
    Skill.fmt(list, { verbose: true }),
  ].join("\n")
}
```

Skills are pre-built instruction packages (stored in `.opencode/skills/`) that the model can load on demand. The system prompt gives the model a summary of available skills; the model then uses the `skill` tool to load a specific skill's full `SKILL.md` instructions when needed.

---

## 15.7 The Assembled Prompt

The full system prompt, assembled in `LLM.stream()`, follows this structure:

```
[System Message 1 - Identity + Instructions]
  1. Provider identity prompt (or agent custom prompt)
  2. SystemPrompt.environment() -- working dir, platform, date
  3. InstructionPrompt.system() -- AGENTS.md, config instructions
  4. SystemPrompt.skills() -- available skill summaries
  5. Custom system prompt from user message (input.user.system)

[System Message 2+ - Plugin additions]
  6. Plugin "experimental.chat.system.transform" additions
```

The identity section and the rest are kept as separate system messages when possible. This enables prompt caching -- the identity section (which rarely changes) can be cached by the provider, saving tokens on subsequent calls.

---

## 15.8 Special Prompt Injections

Several prompt text files are loaded for specific situations:

| File | Injected When | Purpose |
|------|--------------|---------|
| `prompt/plan.txt` | `plan` agent is active | Tells model to produce a structured plan |
| `prompt/build-switch.txt` | Build mode switch | Instructs model to use build commands |
| `prompt/max-steps.txt` | `step >= maxSteps` | Tells model "wrap up, you're running out of steps" |

The `MAX_STEPS` prompt is particularly interesting -- it's injected into the last iteration of the agentic loop:

```
"You are running out of steps. Please wrap up your work and provide
a final response summarizing what you accomplished."
```

This prevents the agent from starting new work when it's about to hit its step limit.

---

## Source File Map

| Concept | File |
|---------|------|
| Provider prompts | `session/system.ts` |
| Environment context | `session/system.ts` (`environment()`) |
| Instruction loading | `session/instruction.ts` |
| Prompt text files | `session/prompt/*.txt` |
| Skill prompts | `session/system.ts` (`skills()`) |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/system-prompt.test.ts` | varies | System prompt assembly, provider selection, environment injection |
| `test/session/instruction.test.ts` | varies | Instruction file discovery, loading priority, claim deduplication |
| `test/session/prompt.test.ts` | 212 | Full prompt assembly including system prompt sections |
