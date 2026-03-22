# Chapter 4: CLI Entry Point -- Parsing Commands with Yargs

> *"Every program begins with `main()`. Ours begins with `yargs.parse()`."*

---

## Introduction

The CLI entry point is where everything starts. When you type `opencode run "build me a blog"`, execution begins in `packages/opencode/src/index.ts`. This chapter traces what happens from process launch through command dispatch.

### What You'll Learn

- How yargs is configured with commands, options, and middleware
- The initialization middleware: logging, environment, database migration
- The command registration pattern
- Error handling and the `NamedError` hierarchy

---

## Notes & Key Points

### 4.1 Entry Point Structure (`src/index.ts`)

The file is a top-level script (not a module export). Execution flow:

1. **Global error handlers**: `process.on("unhandledRejection", ...)` and `process.on("uncaughtException", ...)`
2. **yargs chain**: builds the CLI parser with:
   - `.scriptName("opencode")`
   - `.option("print-logs", ...)`, `.option("log-level", ...)`
   - `.middleware(...)` -- async initialization
   - `.command(...)` -- 20+ command registrations
   - `.fail(...)` -- graceful error formatting
   - `.strict()` -- reject unknown arguments
3. **`await cli.parse()`**: dispatches to the matched command handler
4. **catch block**: formats errors using `FormatError()` and `UI.error()`
5. **finally block**: `process.exit()` to kill any hanging subprocesses (e.g., MCP docker containers)

### 4.2 Initialization Middleware

The `.middleware()` callback runs before any command handler:

```typescript
.middleware(async (opts) => {
  // 1. Initialize logging
  await Log.init({ print, dev, level })
  
  // 2. Set environment markers
  process.env.AGENT = "1"
  process.env.OPENCODE = "1"
  process.env.OPENCODE_PID = String(process.pid)
  
  // 3. One-time database migration
  // Checks if `opencode.db` exists in Global.Path.data
  // If not, runs JsonMigration.run() with progress bar
})
```

The migration progress bar is a nice UX touch -- renders Unicode block characters with orange ANSI colors, handles both TTY and non-TTY output.

### 4.3 Registered Commands

| Command | Module | Purpose |
|---------|--------|---------|
| `run` | `RunCommand` | Execute with a message (headless mode) |
| `serve` | `ServeCommand` | Start the HTTP server |
| `generate` | `GenerateCommand` | Generate agent configs |
| `providers` | `ProvidersCommand` | List/manage providers |
| `agent` | `AgentCommand` | Agent management |
| `models` | `ModelsCommand` | List available models |
| `account` | `ConsoleCommand` | Account management |
| `mcp` | `McpCommand` | MCP server management |
| `upgrade` | `UpgradeCommand` | Self-update |
| `stats` | `StatsCommand` | Usage statistics |
| ... | ... | ... |

### 4.4 The `cmd()` Helper

Commands use a `cmd()` wrapper (`cli/cmd/cmd.ts`) that provides a consistent interface:
- `command` -- the yargs command string
- `describe` -- help text
- `builder` -- option/argument definitions
- `handler` -- the async execution function

### 4.5 Error Handling

The system uses `NamedError` from `@opencode-ai/util/error`:
- Provides `.toObject()` for structured error serialization
- `FormatError()` converts errors to user-friendly messages
- Unknown errors show the log file path for debugging

---

### 4.6 Process Lifecycle: Start to Exit

```
process.start
    |
    v
+-----------------------+
| Global Error Handlers |  process.on("unhandledRejection", ...)
|                       |  process.on("uncaughtException", ...)
+-----------+-----------+
            v
+-----------------------+
| yargs.parse()         |  Builds CLI parser with 20+ commands
+-----------+-----------+
            v
+-----------------------+
| .middleware()          |  Runs BEFORE any command handler:
|                       |  - Log.init() -- configure logging
|                       |  - Set process.env markers (AGENT, OPENCODE, PID)
|                       |  - JsonMigration.run() -- first-time DB setup
|                       |  - Installation.check() -- detect install mode
+-----------+-----------+
            v
+-----------------------+
| Command Handler       |  e.g., RunCommand, TuiCommand, ServeCommand
|                       |  - bootstrap(directory, callback)
|                       |  - Instance.provide() --> Instance.dispose()
+-----------+-----------+
            v
+-----------------------+
| finally block         |  process.exit() -- kills hanging subprocesses
+-----------------------+  (MCP docker, LSP servers, etc.)
```

The `middleware --> command --> finally` structure ensures that:
1. Logging and environment are always set up first
2. Migration runs before any database access
3. Process always exits cleanly, even if MCP containers are still running

### 4.7 Migration Logic: JSON to SQLite

The `JsonMigration.run()` function (`storage/json-migration.ts`) handles one-time migration of legacy data. Early versions of OpenCode stored session data as JSON files on disk. When a user upgrades to a version with SQLite, the migration:

1. Checks if `opencode.db` already exists in `Global.Path.data`
2. If not, scans `Global.Path.data` for JSON session files
3. Loads each JSON session, converts it to the SQLite schema
4. Inserts sessions, messages, and parts into the new database
5. Renders a progress bar during the process (Unicode block characters with ANSI orange)

This migration only runs once -- after the first successful run, the SQLite database exists and the check at step 1 short-circuits.

### 4.8 `Installation.isLocal()` and Install Modes

The `Installation` namespace (`installation/installation.ts`) detects how OpenCode was installed:

- **Local (development)**: running from the git repo via `bun run --cwd packages/opencode src/index.ts`
- **Global (installed)**: installed via `npm install -g opencode` or `bunx opencode`

`Installation.isLocal()` returns `true` when the process is running from a local source tree. This affects:
- **Upgrade behavior**: `opencode upgrade` skips when running locally (you use `git pull` instead)
- **Path resolution**: dev mode resolves assets relative to the source tree; installed mode uses the package directory
- **Telemetry**: local installs may suppress telemetry by default
- **Error display**: local installs show full stack traces; installed builds show user-friendly messages

---

## Source File Map

| Concept | File |
|---------|------|
| CLI entry | `packages/opencode/src/index.ts` |
| Command wrapper | `packages/opencode/src/cli/cmd/cmd.ts` |
| UI helpers | `packages/opencode/src/cli/ui.ts` |
| Error formatting | `packages/opencode/src/cli/error.ts` |
| Log initialization | `packages/opencode/src/util/log.ts` |
| Database migration | `packages/opencode/src/storage/json-migration.ts` |
| Installation detection | `packages/opencode/src/installation/installation.ts` |
