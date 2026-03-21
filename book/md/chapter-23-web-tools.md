# Chapter 23: Web Tools — Fetch and Search

---

## Notes & Key Points

### 23.1 WebFetchTool (`tool/webfetch.ts`)
- Fetches web pages and converts to markdown
- ~6KB implementation
- Handles HTML-to-markdown conversion
- Timeout and size limits
- Used by the model to read documentation (critical for our example prompt!)

### 23.2 WebSearchTool (`tool/websearch.ts`)
- Uses Exa API for web search
- Returns search results with snippets
- Only enabled for Zen users or via `OPENCODE_ENABLE_EXA` flag

---

## 📝 Worked Example: Fetching Next.js Documentation

Our blog prompt explicitly asks the model to "review the documentation at https://nextjs.org/docs." This triggers the webfetch tool early in the session:

```
webfetch({ url: "https://nextjs.org/docs" })
```

**Code path:**
1. The stream processor receives `tool-call` with `toolName: "webfetch"`
2. `resolveTools()` has already wrapped `WebFetchTool` in an AI SDK `tool()` callback
3. The callback creates a `Tool.Context` and calls `WebFetchTool.execute()`
4. Inside execute:
   - Permission check: `ctx.ask({ permission: "webfetch", patterns: ["https://nextjs.org/*"] })`
   - `fetch("https://nextjs.org/docs")` retrieves the page
   - HTML converted to markdown (stripping navigation, scripts, etc.)
   - Output truncated via `Truncate.output()` if it exceeds the configured limit
5. Tool result stored as a completed `ToolPart` with the markdown content
6. The model now has up-to-date Next.js documentation in its context window

**What the user sees in the CLI:**
```
🔧 webfetch → https://nextjs.org/docs
  Read 15,432 chars from nextjs.org
```

The SSE event `message.part.updated` fires → the CLI renders the tool status.

---

## Source File Map

| Tool | File |
|------|------|
| WebFetch | `tool/webfetch.ts` |
| WebSearch | `tool/websearch.ts` |

---

## 🧪 Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/tool/webfetch.test.ts` | 101 | URL fetching, HTML-to-markdown conversion, timeout handling, output size limits |
