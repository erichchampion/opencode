# Chapter 7: The Server — Building an HTTP API with Hono

> *"Every agent needs a nervous system. Ours runs on HTTP."*

---

## Introduction

OpenCode's server is the bridge between clients and the agent engine. Built with Hono, it exposes a comprehensive REST API with OpenAPI documentation, SSE event streaming, and WebSocket support. This chapter explores the server architecture.

### What You'll Learn

- How the Hono app is constructed with routes and middleware
- The route module pattern
- The in-process fetch shortcut for CLI usage
- SSE event streaming for real-time updates
- `Server.listen()` vs. `Server.Default()` (in-process)

---

## Notes & Key Points

### 7.1 Server Construction (`server/server.ts`)

`Server.createApp()` builds a Hono app with:

1. **Error handler** — converts `NamedError`, `HTTPException`, and unknown errors to structured JSON
2. **Auth middleware** — optional basic auth via `OPENCODE_SERVER_PASSWORD`
3. **Logging middleware** — request/response timing
4. **CORS middleware** — allows localhost, tauri, and *.opencode.ai origins
5. **Directory resolution** — reads `x-opencode-directory` header or query param
6. **Instance.provide()** — each request gets a scoped project instance

### 7.2 Route Modules

Routes are organized into focused modules:

| Route | Module | Key Operations |
|-------|--------|---------------|
| `/session` | `SessionRoutes` | Create, list, prompt, cancel, share |
| `/provider` | `ProviderRoutes` | List providers, models |
| `/config` | `ConfigRoutes` | Get/set configuration |
| `/permission` | `PermissionRoutes` | Reply to permission requests |
| `/event` | `EventRoutes` | SSE event stream subscription |
| `/mcp` | `McpRoutes` | MCP server management |
| `/project` | `ProjectRoutes` | Project info, commands |
| `/file` | `FileRoutes` | File serving |
| `/tui` | `TuiRoutes` | TUI-specific endpoints |

### 7.3 The In-Process Fetch Pattern

In `cli/cmd/run.ts`, the CLI creates an SDK client that calls the server without an actual network round trip:

```typescript
const fetchFn = async (input, init) => {
  const request = new Request(input, init)
  return Server.Default().fetch(request)
}
const sdk = createOpencodeClient({
  baseUrl: "http://opencode.internal",
  fetch: fetchFn,
})
```

This means the CLI can use the exact same SDK as a remote client, but with zero-latency in-process calls.

### 7.4 OpenAPI Generation

The server auto-generates OpenAPI specs via `hono-openapi`:
- Routes are decorated with `describeRoute()` for documentation
- Input validation with `validator()` and Zod schemas
- `resolver()` provides schema references for responses
- `generateSpecs()` produces the full OpenAPI 3.1.1 document

### 7.5 Event Streaming

Real-time communication uses SSE:
- Client subscribes via `sdk.event.subscribe()`
- Server streams events: `message.updated`, `message.part.updated`, `session.status`, `permission.asked`, etc.
- The event bus (`Bus.publish()`) feeds events to subscribed clients

---

## Source File Map

| Concept | File |
|---------|------|
| Server creation | `server/server.ts` |
| Session routes | `server/routes/session.ts` |
| Event routes | `server/routes/event.ts` |
| Permission routes | `server/routes/permission.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/server/session-list.test.ts` | 90 | Session listing API endpoint |
| `test/server/session-select.test.ts` | 78 | Session retrieval endpoint |
| `test/server/session-messages.test.ts` | 119 | Message retrieval endpoint |
| `test/server/global-session-list.test.ts` | 89 | Cross-project session listing |
| `test/server/project-init-git.test.ts` | 121 | Project initialization via API |
| `test/control-plane/session-proxy-middleware.test.ts` | 159 | Workspace routing middleware — how requests are proxied to the correct workspace server |
| `test/control-plane/sse.test.ts` | 56 | Server-Sent Events streaming |
| `test/control-plane/workspace-server-sse.test.ts` | 70 | Workspace-level SSE |
| `test/control-plane/workspace-sync.test.ts` | 99 | Workspace state synchronization |

---

### 7.6 End-to-End: Tracing a `POST /session/:id/prompt` Call

Let's trace what happens when the SDK calls `sdk.session.prompt(sessionID, { parts: [{ type: "text", text: "Build me a blog" }] })`:

```
SDK client
    |  POST /session/01HZ.../prompt
    |  Body: { parts: [{ type: "text", text: "Build me a blog" }] }
    v
+---------------------+
| Hono middleware chain|
|  1. CORS check       |
|  2. Auth (if set)    |
|  3. Logging (timing) |
|  4. Directory resolve|
|  5. Instance.provide |
+--------+------------+
         v
+---------------------+
| SessionRoutes.prompt |  server/routes/session.ts
|  1. validator(input) |  Validates input via Zod schema
|  2. SessionPrompt    |  Calls SessionPrompt.prompt(input)
|     .prompt(input)   |    --> creates user message
|                      |    --> enters agentic loop
|  3. Return 200 OK    |  Returns the user message immediately
+---------------------+
         |
         |  (meanwhile, the loop runs asynchronously)
         |
         v
+---------------------+
| Bus.publish(events)  |  Session events stream to:
|  --> SSE subscribers   |  --> EventRoutes SSE endpoint
|  --> TUI renderer      |  --> in-process subscriber
+---------------------+
```

The key design insight: the HTTP response returns *immediately* with the user message. The LLM processing continues asynchronously, with results streamed back via SSE events. This keeps API calls fast and non-blocking.

### 7.7 WebSocket Support

The Hono server supports WebSocket connections via `hono/bun`:

```typescript
import { websocket } from "hono/bun"

// In server.ts, the websocket handler is attached to Bun.serve()
Bun.serve({
  fetch: app.fetch,
  websocket: websocket(app),
})
```

WebSockets are primarily used for:
- **PTY sessions**: interactive terminal sessions for the bash tool, providing real-time bidirectional I/O
- **Event forwarding**: an alternative to SSE for clients that prefer WebSocket connections

The `PtyRoutes` module handles the WebSocket upgrade for pseudo-terminal connections.

### 7.8 Workspace Routing Middleware

The `WorkspaceRouterMiddleware` (`control-plane/workspace-router-middleware.ts`) implements multi-workspace support:

```
Client Request
    |
    v
+-------------------------+
| WorkspaceRouterMiddleware|
|                         |
|  1. Extract workspace ID |  from header or URL
|     (x-opencode-workspace|
|      or query param)     |
|                         |
|  2. Lookup workspace     |  Find workspace server by ID
|     server               |
|                         |
|  3. If local workspace:  |  --> serve directly via Instance.provide()
|     If remote workspace: |  --> proxy to remote workspace server
+-------------------------+
```

This enables the **control plane** architecture: a central server can host multiple workspaces, each potentially running on different machines. The middleware transparently routes requests:

- **Local workspace**: the request is handled in-process, with `Instance.provide()` scoping it to the correct project directory
- **Remote workspace**: the request is proxied to the workspace's dedicated server, using `hono/proxy`

This is what makes the cloud-hosted version of OpenCode possible — the same codebase can run as a local CLI tool or as a multi-tenant workspace server.
