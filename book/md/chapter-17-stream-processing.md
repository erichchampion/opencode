# Chapter 17: Stream Processing — Tokens, Reasoning, and Tool Calls

> *"The agent doesn't think in paragraphs. It thinks in streams."*

---

## Notes & Key Points

### 17.1 The SessionProcessor

`session/processor.ts` — `SessionProcessor.create()` returns a processor that handles:
- Text streaming (start → delta → end)
- Reasoning traces (start → delta → end)
- Tool call lifecycle (input-start → input-delta → tool-call → tool-result/tool-error)
- Step boundaries (start-step → finish-step)
- Error handling and retry logic

### 17.2 Stream Event Types

The `fullStream` async iterator yields events:

| Event | Action |
|-------|--------|
| `start` | Set session status to "busy" |
| `reasoning-start/delta/end` | Create/update/finalize reasoning parts |
| `text-start/delta/end` | Create/update/finalize text parts |
| `tool-input-start` | Create a pending tool part |
| `tool-call` | Transition tool to "running", check for doom loop |
| `tool-result` | Record tool output, mark completed |
| `tool-error` | Record error, check if blocked by permissions |
| `start-step` | Take a filesystem snapshot |
| `finish-step` | Record usage/cost, compute file diff, check compaction |
| `error` | Handle retryable vs. fatal errors |

### 17.3 Doom Loop Detection

When the same tool is called with the same arguments 3 times in a row:
```typescript
if (lastThree.every(p => 
  p.tool === value.toolName && 
  JSON.stringify(p.state.input) === JSON.stringify(value.input)
)) {
  await PermissionNext.ask({ permission: "doom_loop", ... })
}
```
This triggers a permission check that gives the user a chance to break out.

### 17.4 Retry Logic

Retryable errors (rate limits, transient failures) trigger exponential backoff:
- `SessionRetry.retryable()` — classifies errors
- `SessionRetry.delay()` — calculates backoff with jitter
- Session status set to `"retry"` with countdown

### 17.5 Part Persistence

Every part update is persisted to SQLite and published as a bus event:
- `Session.updatePart()` — upsert to `PartTable`
- `Session.updatePartDelta()` — publishes delta event for streaming UI

---

## Source File Map

| Concept | File |
|---------|------|
| Processor | `session/processor.ts` |
| Retry logic | `session/retry.ts` |
| Status tracking | `session/status.ts` |

---

## 🧪 Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/retry.test.ts` | 192 | `SessionRetry.retryable()` error classification, `SessionRetry.delay()` exponential backoff with jitter, rate limit header parsing, transient vs. fatal error distinction |
| `test/memory/abort-leak.test.ts` | 137 | Abort signal handling — verifies no memory leaks when sessions are cancelled mid-stream |
