# Chapter 21: Code Intelligence — Grep, CodeSearch, and LSP

---

## Notes & Key Points

### 21.1 GrepTool (`tool/grep.ts`)
- Wraps ripgrep for fast regex/literal search
- Returns matching lines with context
- Supports path filtering and case sensitivity

### 21.2 CodeSearchTool (`tool/codesearch.ts`)
- Uses Exa API for semantic code search
- Only enabled for OpenCode Zen users or via flag

### 21.3 LspTool (`tool/lsp.ts`)
- Experimental tool for LSP queries (diagnostics, symbols)
- Connects to running LSP servers managed by `lsp/index.ts`

### 21.4 LSP System (`lsp/`)
- `lsp/server.ts` (~65KB) — manages LSP server lifecycle
- `lsp/client.ts` — LSP client protocol implementation
- `lsp/language.ts` — language detection for server selection
- Supports auto-discovery and config-based LSP server definitions
- Provides diagnostics that are used by edit/write tools

---

## Source File Map

| Tool | File |
|------|------|
| Grep | `tool/grep.ts` |
| CodeSearch | `tool/codesearch.ts` |
| LSP Tool | `tool/lsp.ts` |
| LSP System | `lsp/index.ts`, `lsp/server.ts` |

---

## 🧪 Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/tool/grep.test.ts` | 111 | Grep tool execution — regex patterns, literal search, case sensitivity, path filtering |
| `test/file/ripgrep.test.ts` | 54 | Underlying ripgrep binary invocation, output parsing |
| `test/lsp/client.test.ts` | 95 | LSP client protocol — initialization, capability negotiation, request/response |
| `test/lsp/launch.test.ts` | 22 | LSP server process launching and lifecycle |
