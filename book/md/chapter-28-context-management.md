# Chapter 28: Context Management — Compaction, Summarization, and Token Budgets

---

## Notes & Key Points

### 28.1 The Context Window Problem

LLMs have finite context windows. Long conversations exceed them. OpenCode handles this through compaction — summarizing older messages.

### 28.2 Compaction Flow

1. `SessionCompaction.isOverflow()` checks if token usage approaches the model's limit
2. If overflow detected, `SessionCompaction.create()` adds a compaction marker
3. The compaction agent summarizes the older messages
4. The summary replaces the original messages for future inference

### 28.3 Auto-Compaction

When `finish-step` detects token overflow:
```typescript
if (await SessionCompaction.isOverflow({ tokens: usage.tokens, model })) {
  needsCompaction = true
}
```
The loop then schedules compaction automatically.

### 28.4 Context Overflow Recovery

If `streamText()` throws a context overflow error:
```typescript
if (MessageV2.ContextOverflowError.isInstance(error)) {
  needsCompaction = true
}
```
The processor triggers emergency compaction rather than failing.

---

## Source File Map

| Concept | File |
|---------|------|
| Compaction | `session/compaction.ts` |
| Summary | `session/summary.ts` |
| Message filtering | `session/message-v2.ts` (`filterCompacted`) |

---

## 🧪 Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/compaction.test.ts` | 423 | Compaction trigger detection (token count thresholds), summary message generation, compacted message filtering, context window calculation |
| `test/session/message-v2.test.ts` | 930 | `filterCompacted()` — how messages are filtered/rewritten after compaction to maintain context coherence |
| `test/session/revert-compact.test.ts` | 286 | Undoing compaction — restoring the full conversation when the user reverts |
