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

## 26.3 Publishing and Subscribing

```typescript
Bus.publish(Session.Event.Created, { info: session })

Bus.subscribe(Session.Event.Created, (payload) => {
  // payload: { info: Session.Info } -- fully typed
  console.log(`New session: ${payload.info.title}`)
})
```

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

## 26.4 Key Event Categories

| Namespace | Events | Purpose |
|-----------|--------|---------|
| `Session.Event` | Created, Updated, Deleted, Diff, Error | Session lifecycle |
| `MessageV2.Event` | message.updated, part.updated, part.delta, part.removed | Message mutations |
| `Permission.Event` | Asked, Replied | Permission flow |
| `MCP.ToolsChanged` | mcp.tools.changed | MCP server tool list updates |
| `TuiEvent` | ToastShow | TUI notifications |

---

## 26.5 Events and SSE

The server's SSE endpoint (`/events`) subscribes to bus events and forwards them to clients:

```
Bus.publish(Event.Updated) --> SSE subscriber --> JSON event --> Client
```

This is how the TUI and SDK receive real-time updates. Each SSE event carries:
- `type` -- the event name (e.g., `"session.updated"`)
- `data` -- JSON-encoded payload

Cross-reference: Chapter 7 covers the HTTP server and SSE endpoint.

---

## Source File Map

| Concept | File |
|---------|------|
| Bus core | `bus/index.ts` |
| Event definition | `bus/bus-event.ts` |
