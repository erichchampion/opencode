# Chapter 18: The Agentic Loop — Multi-Step Execution and Continuation

> *"The difference between an assistant and an agent is: the agent doesn't stop."*

---

## Notes & Key Points

### 18.1 The Loop Function

`SessionPrompt.loop()` in `session/prompt.ts` is the heart of the agent. It runs a `while(true)` loop:

```
1. Load latest messages
2. Find lastUser, lastAssistant, lastFinished
3. If lastAssistant finished (not tool-calls): EXIT
4. Check for pending subtasks or compactions
5. Otherwise: assemble system prompt, resolve tools, create processor
6. Call processor.process(streamInput)
7. Based on result: "stop" → EXIT, "compact" → schedule compaction, "continue" → loop again
```

### 18.2 Exit Conditions

The loop exits when:
- The model's finish reason is not `tool-calls` or `unknown`
- A permission was rejected (`blocked = true`)
- An unrecoverable error occurred
- The abort signal fired (user cancelled)
- Structured output was captured

### 18.3 Continuation Logic

If the model finishes with `tool-calls` finish reason, the loop continues:
- The model called tools in its response
- Those tools were executed and their results added to history
- The next iteration sends the updated history back to the model

### 18.4 Subtask Handling

If the last message has a pending `subtask` part:
- Creates a child assistant message
- Invokes the `TaskTool` with the subtask's parameters
- The task tool spawns a sub-session with its own agent
- Results flow back into the parent loop

### 18.5 Compaction Handling

If context overflow is detected:
- `SessionCompaction.create()` adds a compaction marker
- On the next loop iteration, `SessionCompaction.process()` summarizes the history
- The compacted summary replaces older messages

### 18.6 Step Counting and Max Steps

```typescript
const maxSteps = agent.steps ?? Infinity
const isLastStep = step >= maxSteps
```

If the model reaches the max step count, a `MAX_STEPS` prompt is injected telling the model to finish up.

### 18.7 Title Generation

On the first step, `ensureTitle()` fires off an async title generation task using the `title` agent — it summarizes the conversation in a few words.

---

## 📝 Worked Example: The Loop in Action for Our Blog Prompt

For our blog-application prompt, the loop typically executes 15–30 iterations. Here's the high-level pattern:

**Iterations 1–3: Research Phase**
- Step 1: Model calls `webfetch` → reads Next.js docs. Finish reason: `tool-calls` → loop continues
- Step 2: Model calls `glob` → checks current directory. Finish reason: `tool-calls` → loop continues
- Step 3: Model emits reasoning about its plan. May call additional tools or proceed to scaffolding

**Iterations 4–6: Scaffolding Phase**
- Step 4: Model calls `bash` → runs `npx create-next-app@latest ...`
  - Permission check fires → user approves → command runs → output captured
  - Finish reason: `tool-calls` → loop continues
- Step 5: Model calls `bash` → `npm install gray-matter remark ...`
- Step 6: Model calls `write` → creates sample markdown post files

**Iterations 7–15: Building Phase**
- Steps 7+: Model alternates between `read` (inspect scaffolding), `edit` (modify pages/components), and `write` (create new files)
- Each iteration: processor handles `tool-call` → `tool-result` → `finish-step` with cost tracking

**Iterations 16–20+: Verification and Iteration Loop**
- Model calls `bash` → `npm run build`
- If build succeeds: model emits final text summary. Finish reason: `stop` → **loop exits**
- If build fails: model reads the error output, calls `edit` to fix the issue, calls `bash` again
- This verify→fix→verify cycle can repeat 2–5 times. Each cycle is one full iteration of the `while(true)` loop

**Exit:**
- `processor.process()` returns `"continue"` throughout tool-call iterations
- On the final text-only response, `lastAssistant.finish === "stop"` → `loop()` breaks
- `SessionCompaction.prune()` cleans up old compaction data
- The final `MessageV2.WithParts` is returned to the caller
- Session status set to `"idle"` → SSE event → CLI exits

---

## Source File Map

| Concept | File |
|---------|------|
| Main loop | `session/prompt.ts` (`SessionPrompt.loop()`) |
| Compaction | `session/compaction.ts` |
| Summary | `session/summary.ts` |

---

## 🧪 Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/compaction.test.ts` | 423 | Compaction trigger detection, summary generation, compacted message filtering — all exercised during loop iteration |
| `test/session/revert-compact.test.ts` | 286 | Reverting to pre-compaction state — the undo mechanism for compaction |
| `test/session/prompt.test.ts` | 212 | Prompt creation and variant resolution that precedes loop entry |
