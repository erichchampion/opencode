# Chapter 23: Web Tools -- Fetch and Search

> *"The internet is the largest reference manual ever written."*

---

## 23.1 Overview

The web tools let the model access external information during a coding session. This is critical for our blog prompt: the model needs to read the Next.js documentation to use the latest APIs correctly.

---

## 23.2 WebFetchTool (`tool/webfetch.ts`)

Fetches a URL and converts the HTML to markdown:

```
webfetch({ url: "https://nextjs.org/docs/getting-started" })
```

Key behaviors:
- **HTTP fetch** -- uses `fetch()` with a configurable timeout
- **HTML-to-markdown conversion** -- the raw HTML is converted to Markdown for the model to read, stripping navigation, ads, and boilerplate
- **Content truncation** -- large pages are truncated via `Truncate.output()` to fit within context limits
- **Error handling** -- HTTP errors, timeouts, and network failures return descriptive messages instead of throwing

### Why Markdown?

Raw HTML is verbose and confusing for LLMs. A single documentation page can be 50,000+ characters of HTML but only 5,000 characters of useful content. The HTML-to-markdown conversion:
1. Strips navigation, headers, footers, scripts, and styles
2. Preserves code blocks, headings, and list structure
3. Reduces token usage by ~10x compared to raw HTML

---

## 23.3 Permission Model

Web fetch requires permission since it makes external network requests:

```typescript
await ctx.ask({
  permission: "webfetch",
  patterns: [params.url],
  always: [new URL(params.url).hostname + "/*"],
})
```

The "always allow" pattern is domain-scoped: approving `nextjs.org/docs/getting-started` also allows all future fetches from `nextjs.org/*`.

---

## 23.4 Worked Example

For our blog prompt `"Review the documentation at https://nextjs.org/docs"`:

1. Model calls `webfetch({ url: "https://nextjs.org/docs" })` -- permission requested
2. User approves (always allow `nextjs.org/*`)
3. The tool fetches the page, converts to markdown, returns ~3,000 tokens of documentation
4. Model reads the markdown, identifies the App Router API, file-based routing conventions
5. Model may make 2-3 follow-up fetches for specific pages (e.g., layout docs, metadata docs)
6. All subsequent `nextjs.org` fetches are auto-approved

---

## 23.5 Web Search Tool (`tool/websearch.ts`)

Performs web searches via the Exa API and returns results as LLM-optimized text:

```
websearch({ query: "Next.js App Router tutorial", numResults: 8, type: "auto" })
```

### Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `query` | required | Search query |
| `numResults` | 8 | Number of results to return |
| `type` | `"auto"` | `"auto"` (balanced), `"fast"` (quick), `"deep"` (comprehensive) |
| `livecrawl` | `"fallback"` | `"fallback"` (cache first) or `"preferred"` (prioritize live) |
| `contextMaxCharacters` | 10,000 | Max characters for context string |

### How It Works

1. Permission checked (query pattern shown to user)
2. JSON-RPC request sent to `https://mcp.exa.ai/mcp` calling `web_search_exa`
3. SSE response parsed to extract content
4. 25-second timeout on the request

### Availability

Like `codesearch`, only available for OpenCode provider users or when `OPENCODE_ENABLE_EXA` is set.

---

## 23.6 Batch Tool (`tool/batch.ts`)

Executes multiple tool calls in parallel:

```
batch({
  tool_calls: [
    { tool: "read", parameters: { filePath: "package.json" } },
    { tool: "read", parameters: { filePath: "tsconfig.json" } },
    { tool: "grep", parameters: { pattern: "TODO" } },
  ]
})
```

Key behaviors:
- **Parallel execution** — all calls run via `Promise.all()` and results are aggregated
- **Max 25 calls** — calls beyond 25 are recorded as errors
- **Cannot nest** — `batch` cannot call itself (prevents recursive parallel execution)
- **No MCP tools** — external tools (MCP, environment) cannot be batched; only built-in tools
- **Individual tracking** — each sub-call gets its own `ToolPart` in the TUI with independent status

This is an experimental tool (requires `experimental.batch_tool: true` in config).

---

## 23.7 Question Tool (`tool/question.ts`)

Asks the user structured questions with predefined options:

```
question({
  questions: [
    { question: "Which database?", header: "Database", options: [
      { label: "PostgreSQL", description: "Relational" },
      { label: "MongoDB", description: "Document" },
    ] }
  ]
})
```

The tool blocks execution until the user responds. Answers are returned formatted and the model continues with the user's choices. Only available when the client is `app`, `cli`, or `desktop` (not available in SDK/API mode).

---

## 23.8 Todo Tools (`tool/todo.ts`)

Two tools for session-scoped task tracking:

**`todowrite`** — updates the session's todo list:
```
todowrite({ todos: [
  { content: "Set up database", status: "completed" },
  { content: "Add auth", status: "in_progress" },
  { content: "Write tests", status: "pending" },
] })
```

**`todoread`** — reads the current todo list. Currently commented out in the registry (the model can use `todowrite` to both read and update).

Todos are stored per-session and displayed in the TUI's sidebar. They help the model track progress on multi-step tasks.

---

## 23.9 Skill Tool (`tool/skill.ts`)

Loads domain-specific instructions into the conversation:

```
skill({ name: "deploy" })
```

Key behaviors:
1. Looks up the skill by name from available SKILL.md files
2. Reads the skill's content (instructions, workflows, commands)
3. Lists up to 10 additional files in the skill directory (scripts, templates)
4. Returns everything wrapped in `<skill_content>` tags

Skills are discovered from `.opencode/skills/` directories. Each skill has a `SKILL.md` with YAML frontmatter (name, description) and markdown instructions.

The skill tool's description dynamically lists available skills, so the model knows what's available before calling it.

---

## Source File Map

| Concept | File |
|---------|------|
| Web fetch | `tool/webfetch.ts` |
| Web search | `tool/websearch.ts` |
| Batch | `tool/batch.ts` |
| Question | `tool/question.ts` |
| Todo | `tool/todo.ts` |
| Skill | `tool/skill.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/tool/webfetch.test.ts` | varies | URL fetching, HTML conversion, timeout, error handling |
| `test/tool/skill.test.ts` | 163 | Skill loading, file listing, content formatting |
