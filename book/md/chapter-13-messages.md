# Chapter 13: Messages — The Data Model Behind Every Turn

> *"Messages are the atoms of conversation."*

---

## Notes & Key Points

### 13.1 Message-Part Architecture

Messages follow a two-tier model:
- **Messages** (`MessageV2.Info`): the top-level container (user or assistant)
- **Parts** (`MessageV2.Part`): content within a message (text, tool calls, reasoning, files, patches)

This separation is key — a single assistant message can contain multiple text blocks, tool invocations, reasoning traces, and file diffs.

### 13.2 Message Types

**User messages** contain:
- `model` — which model to use
- `agent` — which agent to use
- `variant` — reasoning effort level
- `format` — response format (text or JSON schema)
- `system` — optional custom system prompt
- `tools` — tool enable/disable map

**Assistant messages** contain:
- `modelID`, `providerID` — model used
- `agent` — agent that produced this message
- `cost` — token cost in dollars
- `tokens` — input/output/reasoning/cache counts
- `finish` — finish reason (`stop`, `tool-calls`, etc.)
- `error` — if something went wrong

### 13.3 Part Types

| Part Type | Purpose |
|-----------|---------|
| `text` | Model text output |
| `reasoning` | Chain-of-thought reasoning (hidden from user in some UIs) |
| `tool` | Tool invocation with status lifecycle: pending → running → completed/error |
| `file` | Attached files (images, documents) |
| `step-start` / `step-finish` | Step boundaries with token usage/cost |
| `patch` | File changes (git diff format) |
| `compaction` | Context summarization marker |
| `subtask` | Sub-agent task invocation |
| `agent` | Agent reference from `@agent` syntax |

### 13.4 Streaming Parts

Parts are updated incrementally during streaming:
- `Session.updatePart()` — upsert a part
- `Session.updatePartDelta()` — append text delta (published as events for real-time display)

---

## Source File Map

| Concept | File |
|---------|------|
| Message V2 | `session/message-v2.ts` |
| Message (legacy) | `session/message.ts` |
| Schema IDs | `session/schema.ts` |

---

## 🧪 Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/message-v2.test.ts` | 930 | Message creation, part storage/retrieval, delta updates, message filtering for compacted conversations, context overflow detection, role-based message formatting |
| `test/session/structured-output.test.ts` | 386 | Structured output (JSON schema) message handling |
| `test/session/structured-output-integration.test.ts` | 233 | End-to-end structured output with tool calling |
| `test/patch/patch.test.ts` | 348 | `PatchPart` — unified diff generation and application |
| `test/cli/tui/thread.test.ts` | 157 | Thread rendering of message parts in the TUI |
