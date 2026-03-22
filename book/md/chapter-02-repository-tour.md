# Chapter 2: Repository Tour — From Monorepo Root to Source Tree

> *"Good architecture is the art of knowing where things go."*

---

## Introduction

Before diving into execution flow, we need a map. This chapter walks through the monorepo structure, explains the role of each package, and zooms into the `packages/opencode/src/` directory — the heart of the agent engine.

### What You'll Learn

- How the Bun workspace monorepo is organized
- What each top-level package does (opencode, app, sdk, plugin, etc.)
- The 39-directory source tree inside `packages/opencode/src/`
- Naming conventions and file patterns used throughout

---

## Notes & Key Points

### 2.1 Monorepo Structure

The project uses Bun workspaces (`bun.lock`, `bunfig.toml`, workspace definitions in `package.json`).

Top-level directory layout:

```
opencode/
  packages/
    opencode/         # Core agent engine (~64,500 lines of TypeScript)
    app/              # Web app frontend (SolidJS)
    sdk/js/           # TypeScript SDK for programmatic access
    plugin/           # Plugin API definitions
    desktop/          # Tauri-based desktop app
    console/          # Management console
    ui/               # Shared UI component library
    web/              # Marketing/landing page
    util/             # Shared utilities (error types, slugs)
  book/               # This book's source markdown
  .github/            # CI workflows
  bunfig.toml         # Bun configuration
  package.json        # Workspace root with dev scripts
```

Key top-level packages:
- `packages/opencode` -- the core agent engine (CLI, server, session, tools, providers). This is where nearly all of the code lives: 339 TypeScript files across 39 subdirectories.
- `packages/app` — web app frontend (SolidJS)
- `packages/sdk/js` — TypeScript SDK for programmatic access
- `packages/plugin` — plugin API definitions
- `packages/desktop` / `desktop-electron` — Tauri-based desktop app
- `packages/console` — management console
- `packages/ui` — shared UI component library
- `packages/web` — marketing/landing page
- `packages/util` — shared utilities (error types, slugs)

### 2.2 Test and Script Directories

Tests mirror the source tree under `packages/opencode/test/`:

```
packages/opencode/test/
  session/            # Session lifecycle, compaction, prompt, messages
  tool/               # Tool execution, truncation, registry
  provider/           # Provider loading, model resolution
  config/             # Config loading, merging, validation
  cli/                # CLI commands, TUI components
  server/             # API endpoints, SSE events
  plugin/             # Plugin hooks, auth overrides
  auth/               # Credential storage, OAuth flows
  permission/         # Rule evaluation, wildcard matching
  file/               # File operations, gitignore handling
  fixture.ts          # Shared test fixture (creates Instance context)
```

Tests are run from the package directory, never the repo root:

```bash
cd packages/opencode
bun test                       # run all tests
bun test test/session/          # run a specific directory
bun test --test-name-pattern "compaction"  # run by name
```

Build and code generation scripts live in `packages/opencode/script/`.

### 2.3 The Core Source Tree (`packages/opencode/src/`)

39 subdirectories organized by domain concern:

| Directory | Purpose |
|-----------|---------|
| `cli/` | CLI command definitions, UI helpers, bootstrap |
| `server/` | Hono HTTP server and route definitions |
| `session/` | Session management, prompt loop, LLM bridge, messages |
| `agent/` | Agent definitions (build, plan, general, explore, etc.) |
| `provider/` | Multi-provider AI model integration |
| `tool/` | Tool definitions (bash, read, write, edit, grep, etc.) |
| `config/` | Configuration loading, paths, migration |
| `permission/` | Permission evaluation system |
| `bus/` | In-process event bus |
| `snapshot/` | File change tracking via git |
| `mcp/` | Model Context Protocol server integration |
| `lsp/` | Language Server Protocol client management |
| `plugin/` | Plugin loading and lifecycle |
| `project/` | Project detection, instance management, VCS |
| `storage/` | SQLite database (Drizzle ORM) |
| `shell/` | Shell environment detection |
| `file/` | File change tracking, ripgrep integration |
| `skill/` | Skill system (specialized instructions) |
| `question/` | Interactive question handling |
| `format/` | Code formatting integration |
| `auth/` | Authentication credential management |

### 2.4 File Naming Patterns

- `*.ts` — implementation modules
- `*.txt` — prompt templates (embedded via `import PROMPT from "./file.txt"`)
- `*.sql.ts` — Drizzle ORM schema definitions
- `schema.ts` — Zod schema/type definitions
- `index.ts` — namespace barrel exports

### 2.5 Key Entry Files

- `src/index.ts` — CLI entry point (yargs setup)
- `src/cli/bootstrap.ts` — project instance initialization
- `src/server/server.ts` — HTTP server creation
- `src/session/prompt.ts` — main agent orchestration loop

### 2.6 The `catalog:` Workspace Dependency Syntax

Throughout the repo's `package.json` files, you'll see dependencies declared as:

```json
"drizzle-orm": "catalog:",
"hono": "catalog:",
"ai": "catalog:",
```

This is a **Bun workspace catalog** — a centralized version pinning mechanism. The root `package.json` defines a `catalog` section:

```json
{
  "workspaces": {
    "packages": ["packages/*", "packages/sdk/js"],
    "catalog": {
      "ai": "5.0.124",
      "hono": "4.10.7",
      "drizzle-orm": "1.0.0-beta.19-d95b7a4",
      "zod": "4.1.8",
      "effect": "4.0.0-beta.35"
    }
  }
}
```

When a child package declares `"hono": "catalog:"`, Bun resolves it to the version specified in the root catalog. This ensures every package in the monorepo uses exactly the same version of shared dependencies — no more version drift between `packages/opencode` and `packages/app`.

**Why this matters for understanding the codebase:** When you see `catalog:` in `packages/opencode/package.json`, don't go looking for the version there — it's in the root `package.json`'s `catalog` section.

### 2.7 Auxiliary Directories

Beyond `src/`, the `packages/opencode/` directory contains several important auxiliary directories:

| Directory | Purpose |
|-----------|---------|
| `test/` | 111 test files organized into subdirectories mirroring `src/` (e.g., `test/agent/`, `test/session/`, `test/tool/`). Tests use `bun:test` and a shared `fixture.ts` helper for temp directory management. |
| `test/fixture/` | Test infrastructure: `fixture.ts` (temp dir creation with git, config, and `Symbol.asyncDispose`), `fixture.test.ts`, `instance.ts` (instance helpers), `db.ts` (database helpers), mock LSP servers, and sample skill definitions. |
| `migration/` | Drizzle ORM migration files — SQL scripts that evolve the SQLite schema over time. Used by `JsonMigration.run()` during bootstrap. |
| `script/` | Build and release scripts: `build.ts` (compiles the production binary), `version.ts`, and packaging helpers. |
| `specs/` | OpenAPI specification files used for SDK generation and API documentation. |
| `bin/` | The `opencode` shell script entry point that launches the Bun runtime. |

---

## Source File Map

| Concept | File |
|---------|------|
| Monorepo config | `package.json` (workspace definitions) |
| Build config | `bunfig.toml`, `tsconfig.json` |
| Core package | `packages/opencode/package.json` |
| Source root | `packages/opencode/src/` |
