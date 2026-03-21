# Chapter 28: Context Compaction -- Summarizing Long Conversations

> *"Memory is finite; understanding is not."*

---

## 28.1 The Problem

LLMs have fixed context windows. A long coding session with many tool calls and file reads can exhaust this window. When the context fills up, the model either receives an error or loses access to earlier conversation history. Compaction solves this by summarizing older messages into a compact form.

---

## 28.2 How Compaction Works

```
Before:  [msg1, msg2, msg3, msg4, ..., msg50, msg51, msg52]
                                        ^^^^ context limit

After:   [compaction_summary, msg51, msg52]
```

1. **Detection** -- `SessionCompaction.isOverflow()` checks if the total tokens exceed a threshold (typically 80% of the model's context window)
2. **Summary generation** -- a "small" model call summarizes the older messages
3. **Marker insertion** -- a `CompactionPart` is added to the user message, marking where compaction occurred
4. **Tool output clearing** -- old completed tools have their output replaced with `"[Old tool result content cleared]"` via `time.compacted` timestamp

---

## 28.3 The CompactionPart

When compaction runs, it inserts a special part:

```typescript
{
  type: "compaction",
  id: PartID.ascending(),
  messageID: userMessage.id,
  sessionID,
  summary: "The conversation so far has covered setting up a Next.js blog...",
}
```

The `filterCompacted()` function (Chapter 13) reads backward through messages until it finds this marker, including only the messages after it in subsequent LLM calls.

---

## 28.4 Triggering Compaction

Two triggers:

1. **Proactive** -- after each step, `SessionCompaction.isOverflow()` checks token counts. If over threshold, the processor returns `"compact"` and the loop schedules compaction.
2. **Reactive** -- if the LLM returns a `ContextOverflowError`, the processor catches it and triggers immediate compaction.

---

## 28.5 Summary Model

Compaction uses the `small` flag on the LLM call, which selects a cheaper, faster model for summarization. This avoids spending expensive tokens on a task that doesn't require the full model's capabilities.

---

## Source File Map

| Concept | File |
|---------|------|
| Compaction logic | `session/compaction.ts` |
| Overflow detection | `session/compaction.ts` (`isOverflow()`) |
| Compacted message filtering | `session/message-v2.ts` (`filterCompacted()`) |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/compaction.test.ts` | 423 | Overflow detection, summary generation, compacted tool output clearing, filtered message reconstruction |
| `test/session/revert-compact.test.ts` | 286 | Interaction between revert and compaction boundaries |
