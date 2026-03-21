# Chapter 30: The Plugin System — Extending OpenCode

---

## Notes & Key Points

### 30.1 Plugin Architecture

Plugins extend OpenCode without modifying core code. Three plugin types:
- **Copilot plugins** (`plugin/copilot.ts`, ~12.5KB) — GitHub Copilot integration
- **Codex plugins** (`plugin/codex.ts`, ~20.5KB) — OpenAI Codex integration
- **Custom plugins** — user-defined via the plugin API

### 30.2 Plugin Hooks

`Plugin.trigger(hookName, context, data)` fires at key extension points:
- `tool.definition` — modify tool descriptions/parameters
- `tool.execute.before` / `tool.execute.after` — wrap tool execution
- `experimental.text.complete` — post-process model text output
- `experimental.chat.messages.transform` — transform message history
- `experimental.chat.system.transform` — modify system prompt

### 30.3 Custom Plugin Registration

Via `@opencode-ai/plugin` package:
```typescript
export default {
  tool: {
    myTool: {
      description: "...",
      args: { input: z.string() },
      execute: async (args, ctx) => "result"
    }
  }
}
```

---

## Source File Map

| Concept | File |
|---------|------|
| Plugin loader | `plugin/index.ts` |
| Copilot plugin | `plugin/copilot.ts` |
| Codex plugin | `plugin/codex.ts` |
| Plugin API | `packages/plugin/` |

---

## 🧪 Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/plugin/codex.test.ts` | 123 | Codex plugin loading, provider/model registration, tool integration |
| `test/plugin/auth-override.test.ts` | 45 | Plugin auth override — how plugins can inject custom authentication handlers |
| `test/cli/plugin-auth-picker.test.ts` | 120 | Auth picker UI when multiple plugins provide credentials |
