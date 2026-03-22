# Chapter 33: The JavaScript SDK -- Programmatic Access

> *"The SDK is the API's best friend."*

---

## 33.1 Overview

The JavaScript SDK (`packages/sdk/js/`) provides a typed client library for programmatic interaction with the OpenCode server. It's used by external tools, editor extensions, and custom integrations to create sessions, send prompts, and subscribe to events.

### Installation

```bash
npm install @opencode-ai/sdk
```

The SDK has no dependencies beyond the generated types -- it's a thin HTTP client that communicates with the OpenCode server's REST and SSE endpoints.

---

## 33.2 Client Creation

```typescript
import { createClient } from "@opencode-ai/sdk"

const client = createClient({ url: "http://localhost:3000" })
```

The client function returns an object with typed methods for every API endpoint. These types are generated from OpenCode's Zod schemas, ensuring the SDK stays in sync with the server.

### Complete Working Example

```typescript
import { createClient } from "@opencode-ai/sdk"

async function main() {
  const client = createClient({ url: "http://localhost:3000" })

  // Create a session
  const session = await client.session.create({})
  console.log(`Session: ${session.id}`)

  // Subscribe to streaming events
  const unsub = client.event.subscribe((event) => {
    if (event.type === "message.part.delta") {
      process.stdout.write(event.data.delta)
    }
  })

  // Send a prompt
  await client.session.prompt({
    sessionID: session.id,
    parts: [{ type: "text", text: "List the files in this project" }],
  })

  // Wait for completion, then clean up
  setTimeout(() => { unsub(); process.exit(0) }, 30000)
}

main()
```

---

## 33.3 Core Operations

```typescript
// Create a session
const session = await client.session.create({})

// Send a prompt
const response = await client.session.prompt({
  sessionID: session.id,
  parts: [{ type: "text", text: "Create a hello world app" }],
})

// List sessions
const sessions = await client.session.list({})

// Subscribe to events (SSE)
const unsubscribe = client.event.subscribe((event) => {
  if (event.type === "message.part.delta") {
    process.stdout.write(event.data.delta)
  }
})
```

---

## 33.4 Event Subscription

The SDK wraps the SSE endpoint in a typed event emitter:

```typescript
client.event.subscribe((event) => {
  switch (event.type) {
    case "session.updated":
      // event.data: { info: Session.Info }
      break
    case "message.part.delta":
      // event.data: { sessionID, messageID, partID, field, delta }
      break
    case "permission.asked":
      // event.data: Permission.Request
      break
  }
})
```

The event types are discriminated unions -- TypeScript's type narrowing works with the `switch` statement.

---

## 33.5 SDK Generation

The SDK is generated from OpenCode's server route definitions:

```bash
./packages/sdk/js/script/build.ts
```

This script:
1. Extracts Zod schemas from all API routes
2. Converts them to TypeScript types
3. Generates typed client methods for each endpoint
4. Outputs the SDK package to `packages/sdk/js/src/`

This ensures the SDK always matches the server's API surface.

---

## 33.6 Use Cases

| Use Case | Pattern |
|----------|---------|
| Editor extension | Create session, send prompt, subscribe to events for real-time display |
| CI/CD pipeline | Create session, send prompt with `noReply: false`, read final response |
| Custom TUI | Subscribe to all events, render custom interface |
| Batch processing | Create multiple sessions, send prompts in parallel |
| Permission automation | Subscribe to `permission.asked`, auto-reply based on rules |

---

## Source File Map

| Concept | File |
|---------|------|
| SDK source | `packages/sdk/js/src/` |
| SDK build script | `packages/sdk/js/script/build.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/server/session-list.test.ts` | 90 | SDK-style session listing via the HTTP API |
| `test/server/session-select.test.ts` | 78 | SDK-style session retrieval |
| `test/server/session-messages.test.ts` | 119 | SDK-style message retrieval with pagination |
