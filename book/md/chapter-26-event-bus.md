# Chapter 26: The Event Bus — Decoupled Communication

---

## Notes & Key Points

### 26.1 Design

The `Bus` module (`bus/index.ts`, ~2.7KB) provides an in-process pub/sub system:
- `Bus.publish(event, data)` — broadcast an event
- `Bus.subscribe(event, handler)` — listen for events
- Events are typed via TypeScript generics

### 26.2 Key Events

| Event | Publishers | Subscribers |
|-------|-----------|-------------|
| `Session.Event.Created` | Session | Server (SSE), UI |
| `Session.Event.Updated` | Session | Server (SSE), UI |
| `Message.Event.PartUpdated` | Processor | Server (SSE → client) |
| `Permission.Event.Asked` | Permission | Server (SSE → client) |
| `Session.Event.Error` | Processor | CLI (error display) |

### 26.3 SSE Bridge

The server's `EventRoutes` subscribes to the bus and forwards events to clients via Server-Sent Events (SSE). This enables real-time UI updates.

---

## Source File Map

| Concept | File |
|---------|------|
| Bus | `bus/index.ts` |
| Bus events | `bus/bus-event.ts` |

---

## 🧪 Test References

The Bus is tested indirectly through most integration tests — nearly every test that creates sessions or messages verifies event publishing. Key direct tests:

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/acp/event-subscription.test.ts` | 683 | Event subscription patterns, filtering, and lifecycle management |
| `test/control-plane/sse.test.ts` | 56 | SSE event forwarding from Bus to HTTP clients |
| `test/control-plane/workspace-server-sse.test.ts` | 70 | Workspace-level SSE event streaming |
| `test/session/session.test.ts` | 142 | `Bus.subscribe(Session.Event.Created, ...)` — canonical pattern for event subscription (see Chapter 12) |
