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

1. **Detection** -- `SessionCompaction.isOverflow()` checks if the total tokens exceed a threshold
2. **Pruning** -- old tool outputs are cleared to free space immediately
3. **Summary generation** -- the "compaction" agent summarizes the older messages
4. **Marker insertion** -- a `CompactionPart` marks where compaction occurred
5. **Continuation** -- a synthetic user message resumes the conversation

---

## 28.3 Overflow Detection

The `isOverflow()` function from `session/compaction.ts` checks whether the model's usable context is exhausted:

```typescript
export async function isOverflow(input: {
  tokens: MessageV2.Assistant["tokens"]
  model: Provider.Model
}) {
  const config = await Config.get()
  if (config.compaction?.auto === false) return false
  const context = input.model.limit.context
  if (context === 0) return false

  const count =
    input.tokens.total ||
    input.tokens.input + input.tokens.output +
    input.tokens.cache.read + input.tokens.cache.write

  const reserved =
    config.compaction?.reserved ??
    Math.min(COMPACTION_BUFFER, ProviderTransform.maxOutputTokens(input.model))
  const usable = input.model.limit.input
    ? input.model.limit.input - reserved
    : context - ProviderTransform.maxOutputTokens(input.model)
  return count >= usable
}
```

The `COMPACTION_BUFFER` is 20,000 tokens -- space reserved for the model's response. The function compares total token usage against the model's usable context window (total context minus output reservation).

---

## 28.4 Pruning: Clearing Old Tool Output

Before running full compaction, OpenCode prunes old tool outputs to free context space:

```typescript
const PRUNE_MINIMUM = 20_000   // only prune if >20k tokens can be recovered
const PRUNE_PROTECT = 40_000   // protect the most recent 40k tokens of tool output
const PRUNE_PROTECTED_TOOLS = ["skill"]  // never prune skill tool outputs
```

The algorithm walks backward through messages:
1. Skip the most recent 2 user turns (always keep recent context)
2. For completed tool parts beyond the 40,000-token protection window, mark them as compacted
3. Compacted tool outputs are replaced with `"[Old tool result content cleared]"` in subsequent LLM calls

This is a lightweight operation -- it doesn't require an LLM call and can significantly reduce token usage by clearing verbose tool outputs (e.g., large file reads, grep results).

---

## 28.5 The CompactionPart

When compaction runs, it inserts a special part:

```typescript
{
  type: "compaction",
  id: PartID.ascending(),
  messageID: userMessage.id,
  sessionID,
  auto: true,       // true for automatic, false for /compact
  overflow: false,   // true if triggered by ContextOverflowError
}
```

The `filterCompacted()` function (Chapter 13) reads backward through messages until it finds this marker, including only the messages after it in subsequent LLM calls.

---

## 28.6 The Compaction Prompt

The compaction agent receives the full conversation history and this prompt template:

```
Provide a detailed prompt for continuing our conversation above.
Focus on information that would be helpful for continuing the conversation,
including what we did, what we're doing, which files we're working on,
and what we're going to do next.

When constructing the summary, try to stick to this template:
---
## Goal
[What goal(s) is the user trying to accomplish?]

## Instructions
[What important instructions did the user give you that are relevant]

## Discoveries
[What notable things were learned during this conversation]

## Accomplished
[What work has been completed, what is in progress, what is left?]

## Relevant files / directories
[Structured list of relevant files that have been read, edited, or created]
---
```

Plugins can override this prompt via the `experimental.session.compacting` hook.

---

## 28.7 Triggering Compaction

Three triggers:

1. **Proactive (automatic)** -- after each step, `isOverflow()` checks token counts. If over threshold, the processor returns `"compact"` and the loop schedules compaction
2. **Reactive (overflow error)** -- if the LLM returns a `ContextOverflowError`, the processor catches it and triggers immediate compaction
3. **Manual** -- the user types `/compact` in the TUI, which triggers compaction regardless of token counts

Automatic compaction can be disabled via `config.compaction.auto = false`.

---

## 28.8 After Compaction

After the summary is generated, the compaction process:

1. If there was a pending user message that triggered the overflow, it is **replayed** -- a copy is inserted after the compaction summary so the model continues working on it
2. If no replay is needed, a synthetic message says *"Continue if you have next steps, or stop and ask for clarification"*
3. The loop restarts with the compacted context: `[compaction_summary, replayed_message]`

---

## 28.9 Reverting Compaction

Users can undo compaction -- the original messages are not deleted, just filtered. A revert clears the compaction marker and restores the full conversation. This is tested in `test/session/revert-compact.test.ts`.

---

## 28.10 Summary Model

Compaction uses the compaction agent, which selects a model optimal for summarization. If the agent doesn't specify a model, it falls back to the same model the user was chatting with. The `small` flag on hidden agents helps select cheaper models for this task.

---

## Source File Map

| Concept | File |
|---------|------|
| Compaction logic | `session/compaction.ts` |
| Overflow detection | `session/compaction.ts` (`isOverflow()`) |
| Pruning | `session/compaction.ts` (`prune()`) |
| Compacted message filtering | `session/message-v2.ts` (`filterCompacted()`) |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/compaction.test.ts` | 423 | Overflow detection, summary generation, pruning, filtered message reconstruction |
| `test/session/revert-compact.test.ts` | 286 | Reverting compaction, interaction between revert and compaction boundaries |

