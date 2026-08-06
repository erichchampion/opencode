# Chapter 13: Messages -- The Data Model Behind Every Turn

> *"Messages are the atoms of conversation."*

---

## 13.1 The Two-Tier Architecture

Messages in OpenCode follow a two-tier model that reflects how LLMs actually work:

```
Session
  +-- Message (user or assistant) -- the envelope
  |     +-- Part (text)           -- content within the envelope
  |     +-- Part (tool)
  |     +-- Part (reasoning)
  |     +-- Part (step-finish)
  |     +-- Part (patch)
  |     ...
  +-- Message
        +-- Part (text)
        +-- Part (file)
        ...
```

**Messages** (`MessageV2.Info`) are the top-level containers. Each message is either a `user` message or an `assistant` message. They hold metadata about the turn: which model produced it, how much it cost, which agent was active, and whether it errored.

**Parts** (`MessageV2.Part`) are the content within a message. A single assistant message can contain multiple text blocks, tool invocations, reasoning traces, file attachments, and step boundaries -- all interleaved based on the order the LLM streamed them.

This separation is essential because a single LLM response often involves multiple tool calls and text segments. Storing them as flat text would lose the structure needed for the TUI to render them, the compaction system to summarize them, and the revert system to undo them.

---

## 13.2 User Messages

User messages carry metadata about what the user requested:

```typescript
export const User = Base.extend({
  role: z.literal("user"),
  time: z.object({ created: z.number() }),
  // text or JSON schema output format
  format: Format.optional(),
  // which agent should handle this
  agent: z.string(),
  // which model to use
  model: z.object({
    providerID: ProviderID.zod,
    modelID: ModelID.zod,
  }),
  // reasoning effort: default, high, max
  variant: z.string().optional(),
  // custom system prompt override
  system: z.string().optional(),
  // tool enable/disable
  tools: z.record(z.string(), z.boolean()).optional(),
  // populated after the response
  summary: z.object({
    title: z.string().optional(),
    body: z.string().optional(),
    diffs: Snapshot.FileDiff.array(),
  }).optional(),
})
```

The `model` and `agent` fields are captured at prompt time, not at session time. This means users can switch models mid-conversation by specifying a different model in the next prompt.

The `tools` map allows per-prompt tool overrides: `{ "bash": false }` disables the bash tool for just that turn.

---

## 13.3 Assistant Messages

Assistant messages track everything about the model's response:

```typescript
export const Assistant = Base.extend({
  role: z.literal("assistant"),
  time: z.object({
    created: z.number(),
    completed: z.number().optional(),
  }),
  // links to the user message that triggered this
  parentID: MessageID.zod,
  // model that actually responded
  modelID: ModelID.zod,
  providerID: ProviderID.zod,
  // agent that produced this
  agent: z.string(),
  // total cost in dollars
  cost: z.number(),
  tokens: z.object({
    total: z.number().optional(),
    input: z.number(),
    output: z.number(),
    reasoning: z.number(),
    cache: z.object({ read: z.number(), write: z.number() }),
  }),
  finish: z.string().optional(), // "stop", "tool-calls", "length", etc.
  error: z.discriminatedUnion("name", [
    AuthError.Schema,
    OutputLengthError.Schema,
    AbortedError.Schema,
    ContextOverflowError.Schema,
    APIError.Schema,
    // ...
  ]).optional(),
  structured: z.any().optional(), // captured structured output (JSON)
  variant: z.string().optional(),
})
```

The `parentID` field creates a user->assistant pairing. Every assistant message points back to the user message that triggered it. This is how the agentic loop knows which messages form a request-response pair.

The `cost` field aggregates across all steps in the response. It's calculated using `Session.getUsage()` which looks up per-token pricing from the provider's model metadata.

---

## 13.4 The Part Type System

Parts use a discriminated union on the `type` field. Here is the complete list with their purposes:

```typescript
export const Part = z.discriminatedUnion("type", [
  // Model text output
  TextPart,
  // Chain-of-thought (extended thinking)
  ReasoningPart,
  // Tool invocation with state lifecycle
  ToolPart,
  // Attached files (images, documents, resources)
  FilePart,
  // Marks the beginning of an agentic step
  StepStartPart,
  // Marks the end with cost/token data
  StepFinishPart,
  // Git snapshot ID for revert tracking
  SnapshotPart,
  // File changes (unified diff hash + file list)
  PatchPart,
  // Context summarization marker
  CompactionPart,
  // Sub-agent task invocation
  SubtaskPart,
  // Agent reference from @agent syntax
  AgentPart,
  // Record of a retry attempt after error
  RetryPart,
])
```

### ToolPart State Machine

The `ToolPart` is the most complex part type. It tracks a tool call through four states:

```
pending --> running --> completed
                   \--> error
```

```typescript
export const ToolState = z.discriminatedUnion("status", [
  // { status: "pending", input, raw }
  ToolStatePending,
  // { status: "running", input, title, time: { start } }
  ToolStateRunning,
  // { status: "completed", input, output, title, metadata,
  //   time: { start, end, compacted? } }
  ToolStateCompleted,
  // { status: "error", input, error, time: { start, end } }
  ToolStateError,
])
```

Each transition is an `updatePart()` call that replaces the part's data. The `pending` state holds the raw JSON from the LLM before input validation. The `running` state adds a start time. The `completed` state includes the tool's output text, metadata (for TUI display), and optional `attachments` (images from a web fetch, for example).

The `time.compacted` field on completed tools is set during context compaction -- it means the full output has been replaced with `"[Old tool result content cleared]"` to save context space.

### StepFinishPart -- Cost Tracking

Every agentic step ends with a `StepFinishPart`:

```typescript
export const StepFinishPart = PartBase.extend({
  type: z.literal("step-finish"),
  reason: z.string(),       // "stop", "tool-calls", "length"
  snapshot: z.string().optional(),
  cost: z.number(),         // cost for this step
  tokens: z.object({
    total: z.number().optional(),
    input: z.number(),
    output: z.number(),
    reasoning: z.number(),
    cache: z.object({ read: z.number(), write: z.number() }),
  }),
})
```

These accumulate across iterations of the agentic loop. The TUI uses them to show "Step 3/N: $0.02, 1.2K tokens" progress indicators.

---

## 13.5 Streaming Part Updates

Parts are updated incrementally during LLM streaming:

- **`Session.updatePart(part)`** -- upserts a part into the database using `INSERT ... ON CONFLICT DO UPDATE`. This is called for every state transition (pending -> running -> completed).
- **`Session.updatePartDelta(input)`** -- publishes a `PartDelta` event without touching the database. This carries text deltas for real-time display in the TUI. The TUI accumulates these deltas client-side for smooth character-by-character rendering.

```typescript
export const updatePartDelta = fn(z.object({
  sessionID: SessionID.zod,
  messageID: MessageID.zod,
  partID: PartID.zod,
  // "text" for TextPart, "text" for ReasoningPart
  field: z.string(),
  // the new characters
  delta: z.string(),
}), async (input) => {
  Bus.publish(MessageV2.Event.PartDelta, input)
})
```

The key design choice: deltas go through the event bus but not the database. Writing every character to SQLite would be prohibitively slow. Instead, the full text is written once when the part is finalized via `updatePart()`.

---

## 13.6 Message Events

The `MessageV2.Event` namespace defines five events:

| Event | When | Purpose |
|-------|------|---------|
| `message.updated` | `updateMessage()` | New or modified message |
| `message.removed` | `removeMessage()` | Message deleted |
| `message.part.updated` | `updatePart()` | Part created or state changed |
| `message.part.delta` | `updatePartDelta()` | Real-time text streaming |
| `message.part.removed` | `removePart()` | Part deleted |

These events drive the TUI's real-time display, the SSE stream sent to API clients, and the SDK's event subscription API.

---

## 13.7 Converting Messages to Model Format

`MessageV2.toModelMessages()` converts the internal message format to the Vercel AI SDK's `ModelMessage[]` format for sending to LLMs. This is where several important transformations happen:

1. **Tool output formatting** -- completed tool parts become `tool-result` messages, with output passed through `toModelOutput()` (which handles string, object, and attachment formats)
2. **Media injection** -- for providers that don't support images in tool results (most OpenAI-compatible APIs), images are extracted and injected as separate user messages
3. **Compacted content** -- tools with `time.compacted` set have their output replaced with `"[Old tool result content cleared]"`
4. **Interrupted tools** -- pending or running tools (from a cancelled session) are converted to error results with `"[Tool execution was interrupted]"` to satisfy Anthropic's requirement that every `tool_use` must have a corresponding `tool_result`
5. **Error filtering** -- assistant messages with errors (except aborted messages that produced content) are skipped entirely
6. **Reasoning parts** -- chain-of-thought parts are included for the same model but excluded when the model changes mid-conversation

The `supportsMediaInToolResults` flag is provider-specific: Anthropic and Google Gemini 3+ support inline media; OpenAI and others need the user-message workaround.

---

## 13.8 Pagination and Streaming

Messages support cursor-based pagination for large sessions:

```typescript
export const page = fn(z.object({
  sessionID: SessionID.zod,
  limit: z.number().int().positive(),
  before: z.string().optional(),  // base64url-encoded cursor
}), async (input) => {
  // Returns { items: WithParts[], more: boolean, cursor?: string }
})
```

The cursor encodes both `id` and `time`, enabling efficient keyset pagination without OFFSET. The `stream()` function wraps `page()` in an async generator that yields messages in reverse chronological order (newest first), which `Session.messages()` then reverses for the loop.

---

## 13.9 Compaction Filtering

`filterCompacted()` trims the message history to only the messages after the most recent compaction:

```typescript
export async function filterCompacted(
  stream: AsyncIterable<MessageV2.WithParts>) {
  const result = [] as MessageV2.WithParts[]
  const completed = new Set<string>()
  for await (const msg of stream) {
    result.push(msg)
    if (msg.info.role === "user" && completed.has(msg.info.id) &&
        msg.parts.some((part) => part.type === "compaction"))
      break
    if (msg.info.role === "assistant" && msg.info.summary
        && msg.info.finish && !msg.info.error)
      completed.add(msg.info.parentID)
  }
  result.reverse()
  return result
}
```

This finds the most recent compaction boundary by tracking which user messages have completed summary responses, then stops there. Everything before the compaction has already been summarized into the compaction's summary text, so those messages don't need to be sent to the LLM.

Cross-reference: Chapter 28 covers the compaction system in detail.

---

## 13.10 Error Classification

`MessageV2.fromError()` classifies exceptions into typed error objects:

| Error Type | Trigger | Retryable? |
|-----------|---------|------------|
| `AbortedError` | User cancelled (`AbortSignal`) | No |
| `AuthError` | Missing API key (`LoadAPIKeyError`) | No |
| `APIError` | HTTP errors from provider | Depends on status code |
| `ContextOverflowError` | Context window exceeded | Yes (via compaction) |
| `OutputLengthError` | Model hit max output tokens | No |
| `StructuredOutputError` | JSON schema validation failed | Limited |

The `APIError` classification delegates to `ProviderError.parseAPICallError()` which extracts provider-specific details (rate limits, quota errors, server errors) and determines retryability.

Cross-reference: Chapter 16 covers the retry mechanism that uses these error types.

---

## Source File Map

| Concept | File |
|---------|------|
| Message V2 | `session/message-v2.ts` |
| Message (legacy) | `session/message.ts` |
| Schema IDs | `session/schema.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/message-v2.test.ts` | 930 | Message creation, part storage/retrieval, delta updates, message filtering for compacted conversations, context overflow detection, role-based message formatting |
| `test/session/structured-output.test.ts` | 386 | Structured output (JSON schema) message handling |
| `test/session/structured-output-integration.test.ts` | 233 | End-to-end structured output with tool calling |
| `test/patch/patch.test.ts` | 348 | `PatchPart` -- unified diff generation and application |
| `test/cli/tui/thread.test.ts` | 157 | Thread rendering of message parts in the TUI |
