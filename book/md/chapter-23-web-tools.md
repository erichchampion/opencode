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

## Source File Map

| Concept | File |
|---------|------|
| Web fetch | `tool/webfetch.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/tool/webfetch.test.ts` | varies | URL fetching, HTML conversion, timeout, error handling |
