# Chapter 19: Tool Architecture -- Definition, Registry, and Execution

> *"Tools are the hands of the agent."*

---

## 19.1 The Tool.define() Pattern

Every tool in OpenCode is defined using `Tool.define()`:

```typescript
export function define<Parameters, Result>(
  id: string,
  init: Info["init"] | Awaited<ReturnType<Info["init"]>>,
): Info {
  return {
    id,
    init: async (initCtx) => {
      const toolInfo = init instanceof Function ? await init(initCtx) : init
      const execute = toolInfo.execute
      toolInfo.execute = async (args, ctx) => {
        // 1. Validate input through Zod schema
        try { toolInfo.parameters.parse(args) }
        catch (error) { throw new Error(`Invalid arguments: ${error}`) }

        // 2. Execute the tool
        const result = await execute(args, ctx)

        // 3. Truncate output (unless tool handles it)
        if (result.metadata.truncated !== undefined) return result
        const truncated = await Truncate.output(result.output, {}, initCtx?.agent)
        return { ...result, output: truncated.content, metadata: { ...result.metadata, truncated: truncated.truncated } }
      }
      return toolInfo
    },
  }
}
```

The `define()` wrapper adds three things that every tool gets for free:
1. **Input validation** -- args are parsed through the Zod schema; malformed calls get a helpful error
2. **Output truncation** -- `Truncate.output()` limits large outputs to prevent context overflow
3. **Consistent error formatting** -- `formatValidationError` (optional) provides custom validation messages

---

## 19.2 Tool.Context

Every tool execution receives a `Tool.Context`:

```typescript
export type Context = {
  sessionID: SessionID      // which session invoked this
  messageID: MessageID      // which assistant message
  agent: string             // which agent
  abort: AbortSignal        // cancellation
  callID?: string           // unique call identifier
  messages: WithParts[]     // full conversation history
  metadata(input): void     // update TUI display (title, status)
  ask(input): Promise<void> // request user permission
}
```

The `metadata()` callback is called multiple times during tool execution to update the TUI. For example, the bash tool calls it on every stdout chunk to show live output.

The `ask()` callback triggers the permission system. If the user denies, it throws `PermissionNext.RejectedError`, which the processor catches and sets `blocked = true`.

---

## 19.3 The init() Function

`init()` is called once per agentic step when tools are resolved. It receives `InitContext` with the current agent, allowing tools to customize their behavior:

- The `BashTool` uses `init()` to detect the acceptable shell (`bash`, `zsh`, `sh`)
- The `TaskTool` uses `init()` to list available sub-agents based on the caller's permissions
- The `ReadTool` uses `init()` to customize its description with the project's directory

This is why `init()` returns a promise -- it can do async setup work.

---

## 19.4 Output Truncation

`Truncate.output()` applies size limits to tool output:

- **Line limit** (`MAX_LINES`) -- clips output beyond a line count
- **Byte limit** (`MAX_BYTES`) -- clips output beyond a byte count
- When truncated, the full output is written to a temporary file and the path is included in the metadata

Tools can opt out of truncation by setting `result.metadata.truncated` themselves (the `define()` wrapper checks this).

---

## 19.5 ToolRegistry

`tool/registry.ts` manages the complete tool set:

1. **Built-in tools** -- `BashTool`, `ReadTool`, `EditTool`, `WriteTool`, `GlobTool`, `GrepTool`, `WebFetchTool`, `TaskTool`, `SkillTool`, etc.
2. **Custom tools** -- loaded from `.opencode/{tool,tools}/*.{js,ts}` via dynamic import
3. **Plugin tools** -- registered via the plugin system's `tool.register` hook
4. **Model-specific filtering** -- `apply_patch` is only enabled for GPT-5+ models that support unified diff format

`ToolRegistry.tools(model, agent)` returns the complete filtered tool set for a specific model and agent combination.

---

## 19.6 Tool Resolution in the Loop

`resolveTools()` in `session/prompt.ts` bridges the registry and the AI SDK:

1. Calls `ToolRegistry.tools(model, agent)` to get available tools
2. For each tool, creates an AI SDK `tool()` wrapper with an execute callback
3. The callback creates a `Tool.Context`, calls the tool's `execute()`, and pipes results back to `Session.updatePart()`

---

## 19.7 The Invalid Tool Handler

When the model calls a tool that doesn't exist (and `experimental_repairToolCall` can't fix it), the call is routed to the `invalid` tool:

```typescript
// tool/invalid.ts
export const InvalidTool = Tool.define("invalid", {
  description: "...",
  parameters: z.object({ tool: z.string(), error: z.string() }),
  async execute(args) {
    return {
      title: "Invalid tool",
      output: `Tool "${args.tool}" not found. Error: ${args.error}. Available tools: ${availableTools}`,
      metadata: {},
    }
  },
})
```

This gives the model an error message with the list of available tools, letting it self-correct on the next step.

---

## 19.8 Complete Tool Catalog

OpenCode provides 22 built-in tools, organized into functional categories:

### Filesystem Tools

| Tool | ID | Source | Purpose |
|------|-----|--------|---------|
| Read | `read` | `tool/read.ts` | Read file contents with line numbering; supports line ranges and image detection |
| Write | `write` | `tool/write.ts` | Create or overwrite files with complete content |
| Edit | `edit` | `tool/edit.ts` | Search-and-replace within files; generates unified diffs |
| Multi Edit | `multiedit` | `tool/multiedit.ts` | Multiple search-and-replace operations in a single call |
| Apply Patch | `apply_patch` | `tool/apply_patch.ts` | Apply unified diff patches (enabled for GPT-5+ models only) |
| Glob | `glob` | `tool/glob.ts` | Find files by pattern, respects `.gitignore` |
| List | `list` | `tool/ls.ts` | List directory contents with file sizes and types |
| Grep | `grep` | `tool/grep.ts` | Regex search across files using ripgrep |

### Code Intelligence Tools

| Tool | ID | Source | Purpose |
|------|-----|--------|---------|
| LSP | `lsp` | `tool/lsp.ts` | Language Server Protocol operations: go-to-definition, find references, hover, document symbols, call hierarchy |
| Code Search | `codesearch` | `tool/codesearch.ts` | Search external code documentation via Exa API (MCP protocol) |

### Execution Tools

| Tool | ID | Source | Purpose |
|------|-----|--------|---------|
| Bash | `bash` | `tool/bash.ts` | Execute shell commands with Tree-sitter parsing for permission extraction |
| Batch | `batch` | `tool/batch.ts` | Execute up to 25 tool calls in parallel; cannot nest itself |

### Web Tools

| Tool | ID | Source | Purpose |
|------|-----|--------|---------|
| Web Fetch | `webfetch` | `tool/webfetch.ts` | Fetch a URL, convert HTML to markdown, return content |
| Web Search | `websearch` | `tool/websearch.ts` | Web search via Exa API with fast/deep modes and live crawling |

### Orchestration Tools

| Tool | ID | Source | Purpose |
|------|-----|--------|---------|
| Task | `task` | `tool/task.ts` | Spawn a child session with a specific agent (sub-agent pattern) |
| Plan Exit | `plan_exit` | `tool/plan.ts` | Transition from plan agent to build agent with user confirmation |
| Question | `question` | `tool/question.ts` | Ask the user structured questions with predefined options |
| Skill | `skill` | `tool/skill.ts` | Load domain-specific instructions from SKILL.md files |

### State Management Tools

| Tool | ID | Source | Purpose |
|------|-----|--------|---------|
| Todo Write | `todowrite` | `tool/todo.ts` | Update the session's todo list (structured task tracking) |
| Todo Read | `todoread` | `tool/todo.ts` | Read the current session's todo list |

### Error Handling

| Tool | ID | Source | Purpose |
|------|-----|--------|---------|
| Invalid | `invalid` | `tool/invalid.ts` | Catches calls to non-existent tools; returns available tool list for self-correction |

### Conditional Availability

Not all tools are available in every session. The registry filters tools based on:

| Condition | Tools Affected | Rule |
|-----------|---------------|------|
| Model type | `apply_patch` vs `edit`/`write` | GPT-5+ uses `apply_patch`; others use `edit`/`write` |
| Provider | `websearch`, `codesearch` | Only for OpenCode provider or `OPENCODE_ENABLE_EXA` flag |
| Feature flag | `lsp` | `OPENCODE_EXPERIMENTAL_LSP_TOOL` |
| Feature flag | `batch` | Config `experimental.batch_tool: true` |
| Feature flag | `plan_exit` | `OPENCODE_EXPERIMENTAL_PLAN_MODE` + CLI client |
| Client type | `question` | Only for `app`, `cli`, `desktop` clients |
| Agent | (per agent) | Agent permissions deny/allow specific tools per agent |

### Custom Tools

Users can add custom tools by placing `.ts` or `.js` files in `.opencode/tools/`:

```typescript
// .opencode/tools/deploy.ts
export default {
  description: "Deploy to staging",
  args: { env: z.enum(["staging", "prod"]) },
  execute: async (args, ctx) => `Deployed to ${args.env}`,
}
```

These are auto-discovered at startup and receive the same output truncation and permission handling as built-in tools.

---

## Source File Map

| Concept | File |
|---------|------|
| Tool base | `tool/tool.ts` |
| Registry | `tool/registry.ts` |
| Output truncation | `tool/truncate.ts`, `tool/truncate-effect.ts` |
| Invalid tool handler | `tool/invalid.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/tool/registry.test.ts` | 122 | `ToolRegistry.tools()` -- tool discovery, filtering by model/agent, custom tool loading |
| `test/tool/truncation.test.ts` | 162 | `Truncate.output()` -- output size limiting, truncation strategies |
| `test/tool/external-directory.test.ts` | 128 | Permission checks for tools accessing files outside the project directory |
| `test/tool/skill.test.ts` | 163 | Skill tool -- loading SKILL.md instructions for specialized tasks |
