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

## 21.5 LSP Integration

While not a standalone tool, the LSP (Language Server Protocol) integration provides code intelligence data to other tools:

- **WriteTool and EditTool** query LSP diagnostics after file modifications
- Diagnostics (errors, warnings) are included in tool output, helping the model self-correct
- Language servers are started on-demand based on file types

The LSP integration is optional -- if no language server is available, tools work without diagnostics.

---

## Source File Map

| Concept | File |
|---------|------|
| Grep | `tool/grep.ts` |
| Glob | `tool/glob.ts` |
| Ripgrep wrapper | `file/ripgrep.ts` |
| LSP integration | `lsp/index.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/tool/grep.test.ts` | varies | Pattern matching, include/exclude, output formatting |
| `test/file/index.test.ts` | 852 | File operations including gitignore handling |
