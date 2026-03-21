# Chapter 5: Bootstrap — Project Discovery, Database, and Instance Lifecycle

> *"Before the agent can act, it must know where it is."*

---

## Introduction

When OpenCode starts, it needs to discover the project context: What directory are we in? Is this a git repository? What's the worktree root? This chapter covers the bootstrap process that establishes the project instance.

### What You'll Learn

- The `Instance.provide()` pattern for scoped project context
- Project discovery: VCS detection, worktree resolution
- The `InstanceBootstrap` initialization sequence
- `Instance.state()` for lazy, scoped state management
- Database initialization and the Drizzle ORM setup

---

## Notes & Key Points

### 5.1 The Bootstrap Function

```typescript
// cli/bootstrap.ts
export async function bootstrap<T>(directory: string, cb: () => Promise<T>) {
  return Instance.provide({
    directory,
    init: InstanceBootstrap,
    fn: async () => {
      try {
        return await cb()
      } finally {
        await Instance.dispose()
      }
    },
  })
}
```

This establishes a scoped execution context. `Instance.provide()` is the foundation — it creates a project-scoped context that all downstream code can access.

### 5.2 Instance Architecture (`project/instance.ts`)

The `Instance` namespace provides:
- `Instance.directory` — current working directory
- `Instance.worktree` — git worktree root (or directory if no git)
- `Instance.project` — project metadata (ID, VCS type)
- `Instance.state()` — factory for creating lazy, instance-scoped state objects
- `Instance.provide()` — establishes a new instance context (AsyncLocalStorage-like)
- `Instance.dispose()` — cleanup, runs all state destructors

### 5.3 `InstanceBootstrap` Sequence

Located in `project/bootstrap.ts`, this runs during `Instance.provide()`:
1. Detect VCS (git/none)
2. Resolve worktree root
3. Initialize or load the project record from SQLite
4. Start LSP servers if configured
5. Initialize MCP servers if configured
6. Start file watchers

### 5.4 Instance.state() — Lazy Scoped State

A key pattern throughout the codebase:

```typescript
const state = Instance.state(async () => {
  // Expensive initialization, runs once per instance
  return computeState()
})

// Usage — returns the cached value
const data = await state()
```

Used by: `Agent`, `ToolRegistry`, `Config`, `Skill`, and more. Each creates scoped state that's lazily initialized and automatically cleaned up when the instance is disposed.

### 5.5 Database Setup

- SQLite via `better-sqlite3` (through Drizzle ORM)
- Database file: `Global.Path.data + "/opencode.db"`
- Tables created via Drizzle migrations
- `Database.use()` provides transactional database access
- `Database.effect()` — deferred side effects that run after transaction commit

---

## Source File Map

| Concept | File |
|---------|------|
| Bootstrap | `cli/bootstrap.ts` |
| Instance | `project/instance.ts` |
| Instance bootstrap | `project/bootstrap.ts` |
| Project model | `project/project.ts` |
| Database | `storage/db.ts` |
| Global paths | `global/index.ts` |

---

## 🧪 Test References

The test fixture system itself demonstrates the `Instance.provide()` pattern:

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/fixture/fixture.ts` | 74 | The `tmpdir()` helper — creates temp directories, initializes git, writes config, uses `Symbol.asyncDispose` for cleanup. A microcosm of the bootstrap pattern. |
| `test/project/project.test.ts` | 395 | Project discovery, VCS detection, worktree resolution. Tests how `Instance.provide()` resolves project context from a directory path. |
| `test/project/state.test.ts` | 115 | `Instance.state()` — lazy initialization, caching, and disposal of scoped state objects. |
| `test/project/vcs.test.ts` | 123 | VCS detection (git vs. none), branch resolution, worktree root finding. |
| `test/project/worktree-remove.test.ts` | 96 | Worktree cleanup and removal edge cases. |
| `test/project/migrate-global.test.ts` | 140 | Migration of global project data between versions. |
| `test/storage/db.test.ts` | 14 | Basic database initialization verification. |

**Key pattern in `fixture.ts`:**
```typescript
export async function tmpdir(options?) {
  const dirpath = path.join(os.tmpdir(), "opencode-test-" + Math.random().toString(36).slice(2))
  await fs.mkdir(dirpath, { recursive: true })
  if (options?.git) { await $`git init`.cwd(dirpath).quiet() }
  if (options?.config) { await Bun.write(path.join(dirpath, "opencode.json"), JSON.stringify(options.config)) }
  return {
    [Symbol.asyncDispose]: async () => { /* cleanup */ },
    path: realpath,
  }
}
```

This mirrors the production `bootstrap()` → `Instance.provide()` → `Instance.dispose()` lifecycle.

### 5.6 Instance Lifecycle Diagram: Provide → Use → Dispose

```
Instance.provide({ directory, init, fn })
    │
    ├── 1. Filesystem.resolve(directory) — normalize path
    │
    ├── 2. Check cache (Map<string, Promise<Context>>)
    │       │
    │       ├── cache HIT: reuse existing context
    │       │
    │       └── cache MISS:
    │             └── boot({ directory, init })
    │                   ├── Project.fromDirectory(directory)
    │                   │     ├── Detect VCS (git / none)
    │                   │     ├── Resolve worktree root
    │                   │     └── Load or create project record (SQLite)
    │                   │
    │                   ├── context.provide(ctx, init)
    │                   │     └── init() runs inside ALS context
    │                   │           ├── LSP.start()
    │                   │           ├── MCP.init()
    │                   │           └── FileWatcher.start()
    │                   │
    │                   └── Return { directory, worktree, project }
    │
    ├── 3. context.provide(ctx, fn) — run user callback inside ALS
    │       └── fn() has access to Instance.directory, .worktree, .project, .state()
    │
    └── (on exit or explicit call)
        Instance.dispose()
            ├── State.dispose(directory) — runs all state destructors
            ├── disposeInstance(directory) — cleanup Effect runtime
            ├── cache.delete(directory)
            └── GlobalBus.emit("server.instance.disposed")
```

**Key insight:** The `cache` Map ensures that only one `Instance` exists per directory at any time. If two requests arrive for the same project, the second reuses the first's context rather than re-running `boot()`.

### 5.7 The SQL Schema in Detail

The database uses five primary tables, all defined with Drizzle ORM's `sqliteTable()`:

```typescript
// session/session.sql.ts — abbreviated

export const SessionTable = sqliteTable("session", {
  id: text().$type<SessionID>().primaryKey(),
  project_id: text().$type<ProjectID>()
    .references(() => ProjectTable.id, { onDelete: "cascade" }),
  parent_id: text().$type<SessionID>(),      // for sub-tasks
  title: text().notNull(),
  version: text().notNull(),
  share_url: text(),                          // if shared via opencode.ai
  summary_diffs: text({ mode: "json" })       // file change summary
    .$type<Snapshot.FileDiff[]>(),
  permission: text({ mode: "json" })          // session-level permission overrides
    .$type<PermissionNext.Ruleset>(),
  revert: text({ mode: "json" }),             // snapshot data for undo
  ...Timestamps,                              // time_created, time_updated
})

export const MessageTable = sqliteTable("message", {
  id: text().$type<MessageID>().primaryKey(),
  session_id: text().$type<SessionID>()
    .references(() => SessionTable.id, { onDelete: "cascade" }),
  data: text({ mode: "json" }).$type<InfoData>(),  // role, metadata
  ...Timestamps,
})

export const PartTable = sqliteTable("part", {
  id: text().$type<PartID>().primaryKey(),
  message_id: text().$type<MessageID>()
    .references(() => MessageTable.id, { onDelete: "cascade" }),
  session_id: text().$type<SessionID>(),
  data: text({ mode: "json" }).$type<PartData>(),  // text, tool-call, tool-result, etc.
  ...Timestamps,
})

export const TodoTable = sqliteTable("todo", { ... })       // task tracking per session
export const PermissionTable = sqliteTable("permission", { ... })  // persisted "always" grants
```

**Design patterns to note:**
- **JSON columns**: `data` fields store structured JSON (message info, parts, diffs) — keeps the schema flexible while retaining SQLite performance
- **Cascade deletes**: all child tables cascade from their parent. Deleting a session removes all messages, parts, and todos automatically
- **Branded types**: `SessionID`, `MessageID`, `PartID` are branded string types (via `$type<>`) — prevents accidentally passing a session ID where a message ID is expected
- **ULID primary keys**: IDs are ULIDs (Universally Unique Lexicographically Sortable Identifiers) — time-sortable and unique without coordination

### 5.8 AsyncLocalStorage Mechanics Behind Instance

The `Context` utility that powers `Instance` is a thin wrapper around Node.js `AsyncLocalStorage`:

```typescript
// util/context.ts — complete implementation (26 lines)
import { AsyncLocalStorage } from "async_hooks"

export namespace Context {
  export class NotFound extends Error {
    constructor(public override readonly name: string) {
      super(`No context found for ${name}`)
    }
  }

  export function create<T>(name: string) {
    const storage = new AsyncLocalStorage<T>()
    return {
      use() {
        const result = storage.getStore()
        if (!result) throw new NotFound(name)
        return result
      },
      provide<R>(value: T, fn: () => R) {
        return storage.run(value, fn)
      },
    }
  }
}
```

**How it works:**
1. `AsyncLocalStorage.run(value, fn)` creates a new async context with `value`, then runs `fn` within it
2. Any code called from within `fn` — even through `await`, `setTimeout`, or event callbacks — can access `value` via `getStore()`
3. When `fn` exits, the context is automatically cleaned up

**Why this matters for the codebase:** Instead of threading a `project` parameter through every function call, any function anywhere in the call tree can access `Instance.directory`, `Instance.worktree`, or `Instance.project` directly. This is what makes patterns like `Instance.state()` possible — the state factory knows which project it belongs to without being told explicitly.

The `Instance.bind()` method handles edge cases where callbacks escape the async context (native addons, event emitters):

```typescript
bind<F extends (...args: any[]) => any>(fn: F): F {
  const ctx = context.use()
  return ((...args: any[]) => context.provide(ctx, () => fn(...args))) as F
}
```

This captures the current context and re-establishes it when the callback fires.

---

## Questions for Expansion

- [x] Diagram the Instance provide/dispose lifecycle
- [x] Detail the SQL schema (SessionTable, MessageTable, PartTable)
- [x] Explain the AsyncLocalStorage mechanics behind Instance
