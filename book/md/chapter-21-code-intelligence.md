# Chapter 21: Code Intelligence Tools -- Grep, Code Search, and File Discovery

> *"Finding code is half the battle."*

---

## 21.1 Overview

The code intelligence tools help the model navigate and understand the codebase. While the filesystem tools (Chapter 20) operate on individual files, the intelligence tools operate across the entire project -- searching for patterns, finding definitions, and building a mental map of the code.

---

## 21.2 GrepTool (`tool/grep.ts`)

The grep tool wraps `ripgrep` for fast pattern search across the project:

```
grep({ pattern: "SessionPrompt.loop", path: ".", include: "*.ts" })
```

Key behaviors:
- **Uses ripgrep** -- fast, respects `.gitignore`, supports regex
- **Include/exclude filters** -- glob patterns for file type filtering
- **Context lines** -- returns surrounding context for each match
- **Line numbers** -- output includes file path and line number for each match
- **Output format** -- results are structured for the model: `file.ts:42: matching line content`

The output goes through `Truncate.output()`, so very broad searches (e.g., grepping for `import`) are safely truncated.

---

## 21.3 GlobTool (`tool/glob.ts`)

While covered in Chapter 20 as a filesystem tool, glob also serves code intelligence purposes:
- **Project structure discovery** -- `glob({ pattern: "**/*.ts" })` maps the entire codebase
- **Test file discovery** -- `glob({ pattern: "**/*.test.ts" })` finds all tests
- **Config file discovery** -- `glob({ pattern: "*.config.{js,ts}" })` finds configuration

The model typically calls glob early in a session to orient itself before making changes.

---

## 21.4 File Indexing Strategy

OpenCode doesn't maintain a persistent code index. Instead, the model builds its understanding incrementally:

1. **Glob** to discover the project structure
2. **Read** to inspect key files (entry points, configs)
3. **Grep** to find specific patterns and function usages
4. **Read** again to dive into the found files

This approach has a major advantage: it works with any project, any language, with zero setup. There's no index to build, no language server to configure, and no staleness issues.

---

## 21.5 The LSP Tool (`tool/lsp.ts`)

The LSP tool provides direct access to Language Server Protocol operations. Unlike the implicit LSP integration in edit/write tools (which only queries diagnostics), this tool lets the model perform rich code navigation:

### Supported Operations

| Operation | What It Returns |
|-----------|----------------|
| `goToDefinition` | Source location where a symbol is defined |
| `findReferences` | All locations where a symbol is used |
| `hover` | Type information and documentation for a symbol |
| `documentSymbol` | All symbols (functions, classes, variables) in a file |
| `workspaceSymbol` | Search for symbols across the entire workspace |
| `goToImplementation` | Concrete implementations of an interface/abstract method |
| `prepareCallHierarchy` | Entry point for call hierarchy queries |
| `incomingCalls` | Functions that call a given function |
| `outgoingCalls` | Functions called by a given function |

### Usage

```
lsp({ operation: "goToDefinition", filePath: "src/session/prompt.ts", line: 42, character: 15 })
```

Line and character are 1-based (as shown in editors). The tool converts to 0-based for the LSP protocol.

### Availability

The LSP tool is gated behind the `OPENCODE_EXPERIMENTAL_LSP_TOOL` feature flag. It requires a running language server for the target file type — if no server is available, it throws a descriptive error rather than returning empty results.

---

## 21.6 Code Search Tool (`tool/codesearch.ts`)

The code search tool queries external code documentation and examples via the Exa API:

```
codesearch({ query: "React useState hook examples", tokensNum: 5000 })
```

Key behaviors:
- **External API** — sends a JSON-RPC request to `https://mcp.exa.ai/mcp` using the MCP protocol
- **Token control** — `tokensNum` parameter (1,000–50,000) controls how much context to return
- **Permission required** — requires user approval; "always allow" auto-approves all queries
- **SSE response parsing** — the API returns Server-Sent Events which are parsed to extract the content
- **30-second timeout** — requests abort after 30 seconds

### Availability

Only available when using the OpenCode provider or when the `OPENCODE_ENABLE_EXA` feature flag is set.

---

## Source File Map

| Concept | File |
|---------|------|
| Grep | `tool/grep.ts` |
| Glob | `tool/glob.ts` |
| LSP tool | `tool/lsp.ts` |
| Code search | `tool/codesearch.ts` |
| Ripgrep wrapper | `file/ripgrep.ts` |
| LSP integration | `lsp/index.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/tool/grep.test.ts` | varies | Pattern matching, include/exclude, output formatting |
| `test/file/index.test.ts` | 852 | File operations including gitignore handling |
