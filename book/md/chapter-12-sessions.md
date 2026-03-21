# Chapter 12: Sessions -- Creating, Persisting, and Resuming Conversations

> *"Every conversation has a beginning, but a good session management system lets it have a middle too."*

---

## 12.1 What Is a Session?

A session is the top-level container for a conversation between a user and an agent. It holds metadata -- title, timestamps, permission overrides, change summaries -- and owns a chain of messages and their parts. Sessions are persisted in SQLite and survive across restarts. Everything in OpenCode happens *within* a session: prompts, tool calls, compactions, sub-tasks, and reverts.

The `Session` namespace in `session/index.ts` (~900 lines) defines all session operations. It's one of the largest modules in the codebase because sessions touch nearly every subsystem.

---

## 12.2 The Session Data Model

The `Session.Info` type is a Zod-validated object with these fields:

```typescript
export const Info = z.object({
  id: SessionID.zod,          // descending ULID (newest first)
  slug: z.string(),            // human-readable URL-safe identifier
  projectID: ProjectID.zod,    // links session to a project
  workspaceID: WorkspaceID.zod.optional(),
  directory: z.string(),       // project working directory
  parentID: SessionID.zod.optional(),  // for child sessions (sub-tasks)
  title: z.string(),           // auto-generated or user-specified
  version: z.string(),         // OpenCode version that created it
  summary: z.object({
    additions: z.number(),     // lines added across all files
    deletions: z.number(),     // lines removed
    files: z.number(),         // number of files changed
    diffs: Snapshot.FileDiff.array().optional(),
  }).optional(),
  share: z.object({ url: z.string() }).optional(),
  permission: PermissionNext.Ruleset.optional(),
  revert: z.object({
    messageID: MessageID.zod,
    partID: PartID.zod.optional(),
    snapshot: z.string().optional(),
    diff: z.string().optional(),
  }).optional(),
  time: z.object({
    created: z.number(),
    updated: z.number(),
    compacting: z.number().optional(),
    archived: z.number().optional(),
  }),
})
```

### Why Descending ULIDs?

Session IDs use `SessionID.descending()`, which generates ULIDs that sort newest-first. This means `ORDER BY id` returns the most recent session without needing a separate index on `time_created`. It's a subtle optimization: the primary key index doubles as a chronological index.

### The Slug

Each session gets a `Slug.create()` -- a short, human-readable string like `bold-fox-42`. This is used in plan file paths and sharing URLs, avoiding the need to expose raw ULIDs to users.

---

## 12.3 Session Lifecycle

```
                    create()
                       |
                       v
  +----- idle <-----> prompting -----> looping ------+
  |       ^                              |           |
  |       |                              v           |
  |       +-------- compacting <---------+           |
  |       |                                          |
  |       +------ archived (optional) <--------------+
  |                                                  |
  +-------------- deleted (terminal) <---------------+
```

A session moves through these states:

1. **Created** -- `Session.create()` inserts a row, publishes `Event.Created`, and optionally auto-shares
2. **Prompting** -- `SessionPrompt.prompt()` receives user input and enters the agentic loop
3. **Looping** -- `SessionPrompt.loop()` iterates: LLM call -> tool execution -> next iteration
4. **Compacting** -- `SessionCompaction.process()` summarizes history when the context window fills
5. **Idle** -- the loop exits; session is available for new prompts
6. **Archived** -- `setArchived()` soft-deletes (hidden from default list but still exists)
7. **Deleted** -- `remove()` cascades through messages, parts, and children

---

## 12.4 Creating a Session

The `createNext()` function (called by both `create()` and `fork()`) does the following:

```typescript
export async function createNext(input) {
  const result: Info = {
    id: SessionID.descending(input.id),
    slug: Slug.create(),
    version: Installation.VERSION,
    projectID: Instance.project.id,
    directory: input.directory,
    parentID: input.parentID,
    title: input.title ?? createDefaultTitle(!!input.parentID),
    permission: input.permission,
    time: { created: Date.now(), updated: Date.now() },
  }
  Database.use((db) => {
    db.insert(SessionTable).values(toRow(result)).run()
    Database.effect(() => Bus.publish(Event.Created, { info: result }))
  })
  // Auto-share if configured
  if (!result.parentID && (Flag.OPENCODE_AUTO_SHARE || cfg.share === "auto"))
    share(result.id).catch(() => {})
  Bus.publish(Event.Updated, { info: result })
  return result
}
```

Key design decisions:

- **`Database.effect()`** -- the `Event.Created` publish is deferred until the database transaction commits. This prevents event subscribers from seeing an event for a row that might roll back.
- **Auto-sharing** -- if configured, `share()` is called with `.catch(() => {})` -- fire-and-forget. A failed share should never block session creation.
- **Default titles** -- parent sessions get `"New session - {ISO date}"`, child sessions get `"Child session - {ISO date}"`. The `isDefaultTitle()` regex detects these so the TUI can auto-generate better titles later.

---

## 12.5 Forking a Session

`Session.fork()` duplicates a session up to a specified message:

```typescript
export const fork = fn(z.object({
  sessionID: SessionID.zod,
  messageID: MessageID.zod.optional(),
}), async (input) => {
  const original = await get(input.sessionID)
  const title = getForkedTitle(original.title)  // "My chat" -> "My chat (fork #1)"
  const session = await createNext({ ... })
  const msgs = await messages({ sessionID: input.sessionID })

  for (const msg of msgs) {
    if (input.messageID && msg.info.id >= input.messageID) break
    const newID = MessageID.ascending()
    // Clone message and all its parts into the new session
    await updateMessage({ ...msg.info, sessionID: session.id, id: newID })
    for (const part of msg.parts) {
      await updatePart({ ...part, id: PartID.ascending(), messageID: newID, sessionID: session.id })
    }
  }
  return session
})
```

Fork titles increment: `"My chat" -> "My chat (fork #1)" -> "My chat (fork #2)"`. The `getForkedTitle()` function parses the existing title with a regex to find and increment the fork counter.

This is useful when a user wants to explore an alternative approach from a specific point in the conversation without losing the original.

---

## 12.6 Parent-Child Sessions (Sub-Tasks)

When the `TaskTool` spawns a sub-agent, it creates a child session:

```
Parent Session (id: "01ABC...")
  |-- parentID: undefined
  |-- Messages: [user prompt, assistant tool-calls, ...]
  |
  +-- Child Session (id: "01DEF...")
       |-- parentID: "01ABC..."
       |-- agent: "general" (or "explore")
       |-- Messages: [sub-task prompt, sub-agent work, result]
```

Child sessions:
- Have `parentID` set to the parent session's ID
- Get a `"Child session - ..."` default title
- Are never auto-shared (the `!result.parentID` guard prevents it)
- Are recursively deleted when the parent is deleted (`remove()` calls `children()` then `remove()` on each)
- Are hidden from the default session list (the `roots` filter in `list()` excludes children)

Cross-reference: Chapter 24 covers the `TaskTool` that creates child sessions.

---

## 12.7 Sharing and Unsharing

`Session.share()` uploads the session transcript to `opencode.ai`:

```typescript
export const share = fn(SessionID.zod, async (id) => {
  const cfg = await Config.get()
  if (cfg.share === "disabled") throw new Error("Sharing is disabled")
  const { ShareNext } = await import("@/share/share-next")
  const share = await ShareNext.create(id)
  // Store the share URL in the session row
  Database.use((db) => {
    db.update(SessionTable).set({ share_url: share.url }).where(eq(SessionTable.id, id)).returning().get()
  })
  return share
})
```

The `ShareNext` module is dynamically imported (`await import(...)`) to avoid loading the sharing infrastructure unless needed. This is a common pattern in OpenCode for optional features.

`unshare()` removes the remote share via `ShareNext.remove()` and clears the `share_url` column.

---

## 12.8 Session Events

Sessions communicate state changes via the event bus. Every mutation publishes an event:

| Event | Trigger | Payload |
|-------|---------|---------|
| `Session.Event.Created` | `createNext()` | `{ info: Session.Info }` |
| `Session.Event.Updated` | Any setter (`setTitle`, `touch`, `setArchived`, ...) | `{ info: Session.Info }` |
| `Session.Event.Deleted` | `remove()` | `{ info: Session.Info }` |
| `Session.Event.Diff` | Step completion with file changes | `{ sessionID, diff: FileDiff[] }` |
| `Session.Event.Error` | LLM or tool error | `{ sessionID?, error }` |

Events are defined using `BusEvent.define()` with Zod schemas for type-safe payloads. The `Database.effect()` pattern ensures `Created` events fire only after the database write commits.

Cross-reference: Chapter 26 covers the event bus system. Chapter 7 shows how these events become SSE responses.

---

## 12.9 Session Queries

**Listing** -- `Session.list()` is a generator function that yields sessions matching filter criteria:

```typescript
export function* list(input?: {
  directory?: string,
  workspaceID?: WorkspaceID,
  roots?: boolean,    // exclude child sessions
  start?: number,     // updated since timestamp
  search?: string,    // title search (LIKE %query%)
  limit?: number,     // default: 100
}) { ... }
```

**Global listing** -- `Session.listGlobal()` spans all projects and joins `ProjectTable` to include project metadata. It also supports cursor-based pagination and an `archived` filter.

**Messages** -- `Session.messages()` uses `MessageV2.stream()` (an async generator that pages through messages in batches of 50) then reverses the result to return oldest-first.

---

## 12.10 Permission Overrides

Sessions can carry session-scoped permission rules via `setPermission()`. These override the agent's built-in permissions for the duration of that session:

```typescript
export const setPermission = fn(z.object({
  sessionID: SessionID.zod,
  permission: PermissionNext.Ruleset,
}), async (input) => {
  // Updates the permission column and publishes Event.Updated
})
```

The `Ruleset` type (from `permission/service.ts`) is a set of allow/deny rules for specific tools and arguments. When the agentic loop evaluates permissions, it merges the session ruleset with the agent's rules.

Cross-reference: Chapter 25 covers the permission system in detail.

---

## Source File Map

| Concept | File |
|---------|------|
| Session namespace | `session/index.ts` |
| SQL schema | `session/session.sql.ts` |
| Schema types | `session/schema.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/session.test.ts` | 142 | `Session.create()` event emission (`Session.Event.Created`), event ordering (created before updated), step-finish token propagation via Bus events |
| `test/session/messages-pagination.test.ts` | 115 | Message pagination for large sessions |
| `test/server/session-list.test.ts` | 90 | Session listing via the HTTP API |
| `test/server/session-select.test.ts` | 78 | Session selection and retrieval via API |
| `test/server/session-messages.test.ts` | 119 | Retrieving messages for a session via API |
