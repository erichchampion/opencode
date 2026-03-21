# Chapter 19: Tool Architecture — Definition, Registry, and Execution

> *"Tools are the hands of the agent."*

---

## Notes & Key Points

### 19.1 Tool Definition Pattern

Every tool follows the `Tool.define()` pattern:

```typescript
export const ReadTool = Tool.define<Parameters, Metadata>("read", async (initCtx) => ({
  description: "Read a file...",
  parameters: z.object({ filePath: z.string(), ... }),
  async execute(args, ctx) {
    // ... do work ...
    return { title: "Read file.ts", output: contents, metadata: {} }
  }
}))
```

Key points:
- `id` — unique string identifier (matched by the model in tool calls)
- `init()` — called once during tool resolution; can read agent context
- `parameters` — Zod schema, converted to JSON Schema for the model
- `execute()` — receives parsed args and a `Tool.Context`

### 19.2 Tool.Context

Every tool execution receives:
- `sessionID`, `messageID`, `callID` — tracking identifiers
- `agent` — which agent invoked this
- `abort` — AbortSignal for cancellation
- `messages` — full conversation history
- `metadata()` — callback to update the tool's display metadata (title, UI state)
- `ask()` — callback to request user permission

### 19.3 Tool.define() Wrapper

The `define()` function wraps `execute()` with:
1. **Input validation**: parses args through the Zod schema
2. **Output truncation**: `Truncate.output()` limits large outputs to prevent context overflow
3. **Custom error formatting**: `formatValidationError` for better error messages

### 19.4 ToolRegistry

`tool/registry.ts` manages the complete tool set:

1. **Built-in tools**: `BashTool`, `ReadTool`, `EditTool`, `WriteTool`, `GlobTool`, `GrepTool`, `WebFetchTool`, `TaskTool`, etc.
2. **Custom tools**: loaded from `.opencode/{tool,tools}/*.{js,ts}` directories
3. **Plugin tools**: registered via the plugin system
4. **Model-specific filtering**: e.g., `apply_patch` only for GPT-5+ models

### 19.5 Tool Resolution in the Loop

`resolveTools()` in `session/prompt.ts`:
1. Calls `ToolRegistry.tools(model, agent)` to get all available tools
2. Wraps each in an AI SDK `tool()` with the execute callback
3. The callback creates a `Tool.Context` and calls the tool's `execute()`
4. Tool results flow back to `Session.updatePart()`

---

## Source File Map

| Concept | File |
|---------|------|
| Tool base | `tool/tool.ts` |
| Registry | `tool/registry.ts` |
| Output truncation | `tool/truncate.ts`, `tool/truncate-effect.ts` |
| Invalid tool handler | `tool/invalid.ts` |

---

## 🧪 Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/tool/registry.test.ts` | 122 | `ToolRegistry.tools()` — tool discovery, filtering by model/agent, custom tool loading |
| `test/tool/truncation.test.ts` | 162 | `Truncate.output()` — output size limiting, truncation strategies |
| `test/tool/external-directory.test.ts` | 128 | Permission checks for tools accessing files outside the project directory |
| `test/tool/skill.test.ts` | 163 | Skill tool — loading SKILL.md instructions for specialized tasks |
