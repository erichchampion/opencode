# Chapter 33: The SDK — Programmatic Access

---

## Notes & Key Points

### 33.1 SDK Package

`packages/sdk/js/` provides a typed TypeScript SDK for programmatic access:
- Generated from the OpenAPI spec (auto-generated from Hono routes)
- `createOpencodeClient({ baseUrl, fetch })` — creates a typed client

### 33.2 SDK Capabilities

```typescript
const sdk = createOpencodeClient({ baseUrl: "http://localhost:4096" })

// Session management
await sdk.session.create({})
await sdk.session.prompt({ sessionID, parts: [{ type: "text", text: "..." }] })
await sdk.session.cancel({ sessionID })

// Events
sdk.event.subscribe(["session.updated", "message.part.updated"], handler)

// Provider info
await sdk.provider.list()
await sdk.provider.model.list()
```

### 33.3 In-Process vs. Remote

The SDK can connect to:
- **In-process** — via custom `fetch` that calls `app.fetch()` directly (zero-latency)
- **Remote** — via HTTP to a running `opencode serve` instance
- Same API, same types, different transport

### 33.4 SDK Generation

Run `./packages/sdk/js/script/build.ts` to regenerate from OpenAPI spec.

---

## Source File Map

| Concept | File |
|---------|------|
| SDK source | `packages/sdk/js/` |
| Build script | `packages/sdk/js/script/build.ts` |
| OpenAPI spec | Generated via `Server.openapi()` |

---

## 🧪 Test References

The SDK is tested indirectly through the server API tests, which validate the same HTTP endpoints the SDK calls:

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/server/session-list.test.ts` | 90 | Session listing API — the endpoint backing `sdk.session.list()` |
| `test/server/session-select.test.ts` | 78 | Session retrieval API — backing `sdk.session.get()` |
| `test/server/session-messages.test.ts` | 119 | Message retrieval API — backing `sdk.session.messages()` |
| `test/server/global-session-list.test.ts` | 89 | Cross-project session listing |
| `test/server/project-init-git.test.ts` | 121 | Project initialization API |
| `test/control-plane/session-proxy-middleware.test.ts` | 159 | Session proxy routing — how the SDK connects to workspace servers |
