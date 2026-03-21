# Chapter 15: System Prompt Construction — Building the Model's Instructions

> *"The system prompt is the agent's DNA."*

---

## Notes & Key Points

### 15.1 System Prompt Sources

The system prompt is assembled from multiple layers in `session/prompt.ts`:

```typescript
const system = [
  ...SystemPrompt.environment(model),   // environment context
  ...SystemPrompt.skills(agent),        // available skills
  ...InstructionPrompt.system(),        // .opencode/instructions files
]
```

### 15.2 Provider-Specific Base Prompts

`SystemPrompt.provider(model)` selects a base prompt based on model family:
- `PROMPT_ANTHROPIC` — for Claude models
- `PROMPT_CODEX` — for GPT-5+ models
- `PROMPT_BEAST` — for GPT-4/o1/o3 models
- `PROMPT_GEMINI` — for Gemini models
- `PROMPT_DEFAULT` — fallback
- `PROMPT_TRINITY` — for Trinity models

### 15.3 Environment Block

```
You are powered by the model named claude-sonnet-4-20250514.
<env>
  Working directory: /path/to/project
  Workspace root folder: /path/to/repo
  Is directory a git repo: yes
  Platform: darwin
  Today's date: Thu Mar 20 2025
</env>
```

### 15.4 Skills System

If the `skill` tool is not disabled for the agent, available skills are listed in the system prompt:
- Each skill has a name and description
- The model can use the `skill` tool to load specialized instructions

### 15.5 Instruction Files

`InstructionPrompt.system()` reads user-defined instructions from:
- `.opencode/instructions.md` in the project
- Custom instruction paths in config

### 15.6 Plugin Hooks

`Plugin.trigger("experimental.chat.system.transform", ...)` allows plugins to modify the system prompt before it's sent.

---

## Source File Map

| Concept | File |
|---------|------|
| System prompt | `session/system.ts` |
| Instruction loading | `session/instruction.ts` |
| Base prompts | `session/prompt/*.txt` |
| Skill definitions | `skill/skill.ts` |

---

## 🧪 Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/system.test.ts` | 59 | Provider-specific base prompt selection, environment block construction |
| `test/session/instruction.test.ts` | 170 | Loading user-defined instructions from `.opencode/instructions.md`, instruction file discovery, instruction merging |
| `test/skill/skill.test.ts` | 388 | Skill loading, SKILL.md parsing, skill listing for system prompt injection |
| `test/skill/discovery.test.ts` | 116 | Skill discovery from `.opencode/skill/`, `_agents/skills/`, and index files |
