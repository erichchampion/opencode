# Chapter 17: Stream Processing -- From LLM Events to Persistent State

> *"A stream is not just data in motion -- it's a state machine in disguise."*

---

## 17.1 The Processor's Role

`SessionProcessor` in `session/processor.ts` sits between the raw LLM stream and OpenCode's persistent state. It consumes the `fullStream` from `streamText()` and translates each event into database writes, bus events, and state transitions. The processor also handles retries, doom loop detection, and compaction triggers.

```
streamText()  -->  fullStream  -->  SessionProcessor.process()  -->  Database + Events
```

---

## 17.2 Creating a Processor

`SessionProcessor.create()` returns a stateful object that tracks the current step:

```typescript
export function create(input: {
  assistantMessage: MessageV2.Assistant
  sessionID: SessionID
  model: Provider.Model
  abort: AbortSignal
}) {
  const toolcalls: Record<string, MessageV2.ToolPart> = {}
  let snapshot: string | undefined
  let blocked = false
  let attempt = 0
  let needsCompaction = false

  return {
    get message() { return input.assistantMessage },
    async process(streamInput: LLM.StreamInput) { ... },
  }
}
```

The processor is created fresh for each agentic step. It holds:
- `toolcalls` -- a map of in-flight tool calls by their call ID
- `snapshot` -- the current git snapshot ID for file change tracking
- `blocked` -- whether a permission was rejected
- `attempt` -- retry counter
- `needsCompaction` -- whether context overflow was detected

---

## 17.3 The Stream Event Loop

The core of `process()` is a `for await` loop over the stream's `fullStream`:

```typescript
const stream = await LLM.stream(streamInput)
for await (const value of stream.fullStream) {
  input.abort.throwIfAborted()
  switch (value.type) {
    case "start":              // stream started
    case "reasoning-start":    // extended thinking begins
    case "reasoning-delta":    // thinking text chunk
    case "reasoning-end":      // thinking complete
    case "tool-input-start":   // tool call being assembled
    case "tool-call":          // tool ready to execute
    case "tool-result":        // tool finished successfully
    case "tool-error":         // tool failed
    case "error":              // stream error
    case "start-step":         // new agentic step
    case "finish-step":        // step complete
    case "text-start":         // text output begins
    case "text-delta":         // text chunk
    case "text-end":           // text output complete
    case "finish":             // stream done
  }
}
```

Each event type maps to specific actions. Here are the key ones:

---

## 17.4 Text Events

```
text-start --> text-delta (repeated) --> text-end
```

- **`text-start`** -- creates a new `TextPart` with an empty string and saves it to the database
- **`text-delta`** -- appends the chunk to the in-memory text and publishes a `PartDelta` event (for real-time TUI display) *without* a database write
- **`text-end`** -- trims trailing whitespace, calls the `experimental.text.complete` plugin hook, and writes the final text to the database

The key optimization: deltas go through the event bus but not SQLite. Only the final text hits the database, avoiding hundreds of writes per response.

---

## 17.5 Reasoning Events

```
reasoning-start --> reasoning-delta (repeated) --> reasoning-end
```

Reasoning parts follow the same pattern as text parts but are stored separately as `ReasoningPart` entries. The reasoning map tracks parts by their stream ID, since multiple reasoning blocks can occur within a single response.

---

## 17.6 Tool Events

```
tool-input-start --> tool-call --> tool-result | tool-error
```

The tool lifecycle in the processor:

1. **`tool-input-start`** -- creates a `ToolPart` in `pending` state with empty input
2. **`tool-call`** -- transitions the part to `running` state, records the parsed input, and checks for doom loops
3. **`tool-result`** -- transitions to `completed` with the output, title, metadata, and timing
4. **`tool-error`** -- transitions to `error` state; if the error is a `PermissionNext.RejectedError`, sets `blocked = true`

### Doom Loop Detection

Before executing a tool call, the processor checks for repetitive behavior:

```typescript
const lastThree = parts.slice(-DOOM_LOOP_THRESHOLD)  // DOOM_LOOP_THRESHOLD = 3
if (lastThree.length === DOOM_LOOP_THRESHOLD &&
    lastThree.every(p => p.type === "tool" &&
      p.tool === value.toolName &&
      JSON.stringify(p.state.input) === JSON.stringify(value.input)))
{
  await PermissionNext.ask({ permission: "doom_loop", ... })
}
```

If the model calls the same tool with the same input three times in a row, the processor triggers a `doom_loop` permission check. The user can approve (letting the loop continue if it's intentional) or reject (stopping the session).

> [!IMPORTANT]
> **Security consideration**: Without doom loop detection, a model stuck in a loop could run up arbitrarily large API bills, repeatedly write the same incorrect file content, or execute the same destructive command. The 3-call threshold is a safety net that catches most stuck models while allowing legitimate repeated operations (like polling a build log) when the user explicitly approves.

---

## 17.7 Step Events

```
start-step --> (text/tool events) --> finish-step
```

- **`start-step`** -- captures a git snapshot via `Snapshot.track()` and creates a `StepStartPart`
- **`finish-step`** -- the most complex event handler:
  1. Computes cost and token usage via `Session.getUsage()`
  2. Accumulates cost on the assistant message
  3. Creates a `StepFinishPart` with token breakdown
  4. Takes a new snapshot and generates a diff (`Snapshot.patch()`)
  5. If files changed, creates a `PatchPart` with the diff hash and file list
  6. Triggers `SessionSummary.summarize()` (async, non-blocking)
  7. Checks for context overflow via `SessionCompaction.isOverflow()`

---

## 17.8 Error Handling and Retries

When the stream throws an error, the processor classifies it:

```typescript
catch (e) {
  const error = MessageV2.fromError(e, { providerID: input.model.providerID })
  if (MessageV2.ContextOverflowError.isInstance(error)) {
    needsCompaction = true  // triggers compaction on return
  } else {
    const retry = SessionRetry.retryable(error)
    if (retry !== undefined) {
      attempt++
      const delay = SessionRetry.delay(attempt, error)
      SessionStatus.set(sessionID, { type: "retry", attempt, message: retry, next: Date.now() + delay })
      await SessionRetry.sleep(delay, input.abort)
      continue  // retry the entire stream
    }
    // Non-retryable error -- record on the message and stop
    input.assistantMessage.error = error
  }
}
```

Retryable errors (rate limits, server errors) trigger exponential backoff with jitter. The `SessionStatus.set({ type: "retry" })` call updates the TUI's status indicator.

---

## 17.9 Process Return Values

`process()` returns one of three strings:

| Return | Meaning | Loop Action |
|--------|---------|-------------|
| `"continue"` | Step finished normally | Loop continues to next iteration |
| `"compact"` | Context overflow detected | Loop triggers compaction |
| `"stop"` | Permission blocked, error, or abort | Loop exits |

The agentic loop (Chapter 18) uses these to decide what to do next.

---

## 17.10 Cleanup

After the stream completes (or errors), the processor:
1. Takes a final snapshot diff if one was in progress
2. Marks any pending/running tool parts as `error` with "Tool execution aborted"
3. Sets `time.completed` on the assistant message
4. Persists the final message state

This ensures no tool parts are left in an inconsistent state, even if the stream was cancelled or errored.

---

## Source File Map

| Concept | File |
|---------|------|
| Processor | `session/processor.ts` |
| Retry logic | `session/retry.ts` |
| Session status | `session/status.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/compaction.test.ts` | 423 | Compaction trigger during processing |
| `test/session/message-v2.test.ts` | 930 | Part creation and updates that the processor drives |
| `test/session/prompt.test.ts` | 212 | End-to-end prompt processing |
