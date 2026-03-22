# Chapter 26: The Event Bus -- Typed Events and Subscribers

> *"Loose coupling through structured communication."*

---

## 26.1 Overview

The event bus (`bus/index.ts`) is OpenCode's internal pub-sub system. It decouples producers (session mutations, tool executions) from consumers (TUI rendering, SSE streaming, API responses). Every significant state change in OpenCode flows through the bus.

---

## 26.2 BusEvent.define()

Events are defined with string names and Zod schemas:

```typescript
export const Event = {
  Created: BusEvent.define("session.created", z.object({ info: Session.Info })),
  Updated: BusEvent.define("session.updated", z.object({ info: Session.Info })),
  Deleted: BusEvent.define("session.deleted", z.object({ info: Session.Info })),
  Diff:    BusEvent.define("session.diff",    z.object({ sessionID, diff: FileDiff.array() })),
  Error:   BusEvent.define("session.error",   z.object({ sessionID, error: z.any() })),
}
```

This provides:
1. **Type safety** -- subscribers get typed payloads
2. **Runtime validation** -- published data is validated against the schema
3. **Discoverability** -- all events are defined in one place per module

---

## 26.3 How Bus.publish() Works

From `bus/index.ts`, the `publish()` function delivers events to two destinations:

```typescript
export async function publish<Definition extends BusEvent.Definition>(
  def: Definition,
  properties: z.output<Definition["properties"]>,
) {
  const payload = { type: def.type, properties }
  // 1. Deliver to instance-scoped subscribers (matching type + wildcard "*")
  for (const key of [def.type, "*"]) {
    const match = [...(state().subscriptions.get(key) ?? [])]
    for (const sub of match) {
      pending.push(sub(payload))
    }
  }
  // 2. Forward to GlobalBus for cross-instance delivery (SSE, other instances)
  GlobalBus.emit("event", { directory: Instance.directory, payload })
  return Promise.all(pending)
}
```

The key insight: events are delivered to **both** local subscribers (via `Instance.state()`) and the global bus. This is what enables the SSE streaming -- the server's event route subscribes to the `GlobalBus`, not individual instance buses.

---

## 26.4 Instance Bus vs. Global Bus

OpenCode has two bus layers:

| Layer | Scope | Used By |
|-------|-------|---------|
| **Instance Bus** (`Bus`) | Scoped to one project directory via `Instance.state()` | TUI components, tool callbacks, session processor |
| **Global Bus** (`GlobalBus`) | Process-wide, spans all instances | SSE endpoint, inter-workspace events, shutdown |

When an instance is disposed, the instance bus publishes `InstanceDisposed` to its wildcard subscribers, allowing cleanup of long-lived listeners.

---

## 26.5 Subscribing and Unsubscribing

```typescript
// Type-safe subscription -- callback receives { type, properties } with full typing
const unsub = Bus.subscribe(Session.Event.Created, (event) => {
  console.log(`New session: ${event.properties.info.title}`)
})

// One-shot subscription -- automatically unsubscribes when callback returns "done"
Bus.once(Permission.Event.Replied, (event) => {
  if (event.properties.requestID === myRequest) return "done"
})

// Wildcard subscription -- receives ALL events (used by SSE endpoint)
const unsub = Bus.subscribeAll((event) => {
  stream.write(`data: ${JSON.stringify(event)}\n\n`)
})
```

The `subscribe()` function returns an unsubscribe function. Calling it removes the callback from the subscription list, preventing memory leaks.

### Database.effect()

When publishing inside a database transaction, use `Database.effect()`:

```typescript
Database.use((db) => {
  db.insert(SessionTable).values(toRow(result)).run()
  Database.effect(() => Bus.publish(Event.Created, { info: result }))
})
```

This defers the publish until the transaction commits, preventing subscribers from seeing events for data that might roll back.

---

## 26.6 Complete Event Catalog

All events defined across the codebase:

| Namespace | Event | Trigger |
|-----------|-------|---------|
| `Session.Event` | `session.created`, `.updated`, `.deleted` | Session lifecycle changes |
| `Session.Event` | `session.diff` | File changes detected in a session |
| `Session.Event` | `session.error` | Unhandled session error |
| `MessageV2.Event` | `message.updated` | Message metadata changed |
| `MessageV2.Event` | `part.updated`, `part.delta`, `part.removed` | Message part mutations (text, tools) |
| `Permission.Event` | `permission.asked`, `permission.replied` | Permission request flow |
| `Question.Event` | `question.asked`, `.replied`, `.rejected` | User question flow |
| `SessionCompaction.Event` | `session.compacted` | Compaction completed |
| `MCP` | `mcp.tools.changed`, `mcp.browser.open.failed` | MCP server events |
| `LSP` | `lsp.updated`, `lsp.diagnostics` | Language server changes |
| `File.Event` | `file.edited` | File modification via tools |
| `FileWatcher` | `file.watcher.updated` | Filesystem change detected |
| `Pty` | `pty.created`, `.updated`, `.exited`, `.deleted` | Terminal process lifecycle |
| `Installation` | `installation.updated`, `.update.available` | Version check events |
| `TuiEvent` | `tui.toast.show`, `tui.prompt.append`, `tui.session.select` | TUI-specific events |
| `Command.Event` | `command.executed` | Slash command executed |
| `Project.Event` | `project.updated` | Project metadata changed |
| `VCS.Event` | `vcs.branch.updated` | Git branch change |
| `Bus` | `server.instance.disposed` | Instance shutdown |

---

## 26.7 Event Flow: Tool Execution to UI

A complete event flow showing how a tool execution reaches the TUI:

```
Tool completes (e.g., EditTool writes a file)
    |
    v
Session.updatePart(tool.part)    -- updates SQLite
    |
    v
Bus.publish(MessageV2.Event.PartUpdated)
    |
    +-- Instance subscribers: TUI Thread component re-renders
    |
    +-- GlobalBus.emit("event")
            |
            v
        SSE endpoint streams JSON to SDK clients
```

Cross-reference: Chapter 7 covers the HTTP server and SSE endpoint.

---

## Source File Map

| Concept | File |
|---------|------|
| Bus core | `bus/index.ts` |
| Event definition | `bus/bus-event.ts` |
| Global bus | `bus/global.ts` |
| SSE event route | `server/routes/event.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/compaction.test.ts` | 423 | Events published during compaction |
| `test/server/event.test.ts` | varies | SSE event streaming via GlobalBus |

