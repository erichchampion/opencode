# Chapter 18: The Agentic Loop -- Multi-Step Execution and Continuation

> *"The difference between an assistant and an agent is: the agent doesn't stop."*

---

## 18.1 The Loop Function

`SessionPrompt.loop()` in `session/prompt.ts` is the heart of the agent. It runs a `while(true)` loop that continues calling the LLM until the model produces a final text response:

```
loop() {
  while (true) {
    1. Load latest messages (with compaction filtering)
    2. Find lastUser, lastFinished (last assistant message with data)
    3. Check for pending subtasks or compactions
    4. If context overflow detected, trigger compaction
    5. Resolve model, agent, system prompt, tools
    6. Create assistant message and processor
    7. Call processor.process(streamInput)
    8. Based on result: "stop" -> EXIT, "compact" -> schedule compaction, "continue" -> loop again
  }
}
```

Each iteration is one "step" -- a complete LLM call that may include text output, tool calls, and their results. A typical coding task takes 15-30 steps.

---

## 18.2 Exit Conditions

The loop exits when any of these conditions is met:

| Condition | How Detected | Typical Cause |
|-----------|-------------|---------------|
| Model says "stop" | `finish !== "tool-calls"` and no pending tasks | Model gave a final text answer |
| Permission blocked | `processor.process()` returns `"stop"` | User rejected a tool permission |
| Error occurred | `assistantMessage.error` is set | API error, auth failure, etc. |
| Abort signal | `abort.throwIfAborted()` | User cancelled (Ctrl-C) |
| Structured output | `structuredOutput` was captured | Model called the StructuredOutput tool |

The most common path: the model finishes with `tool-calls` for 10-20 steps, then produces a text-only response with `finish: "stop"`.

---

## 18.3 Continuation Logic

When the model finishes with `tool-calls`, the processor returns `"continue"` and the loop iterates:

1. Messages are reloaded (now including the tool results from the previous step)
2. The updated history is sent back to the model
3. The model sees its previous tool calls and their results
4. It decides what to do next: more tools, or a final answer

This is the fundamental agentic pattern -- the model calls tools, sees results, and decides autonomously whether to continue or stop.

---

## 18.4 Subtask Handling

If the last message has a pending `subtask` part (from the `TaskTool`):

1. The loop creates a child assistant message
2. Invokes `TaskTool.execute()` with the subtask's parameters
3. The task tool spawns a child session with its own agent and loop
4. Results flow back as a completed tool part
5. The parent loop continues with the subtask result in history

If the subtask was triggered by a `/command`, a synthetic user message is injected afterward: "Summarize the task tool output above and continue with your task." This prevents model errors from some providers that require alternating user/assistant messages.

---

## 18.5 Compaction Handling

Context overflow triggers compaction in two ways:

1. **`processor.process()` returns `"compact"`** -- overflow detected during stream processing
2. **Context overflow error** -- the LLM API returned a 400 error about context length

On the next loop iteration:
```typescript
if (task?.type === "compaction") {
  const result = await SessionCompaction.process({
    messages, parentID: lastUser.id, abort, sessionID,
    auto: task.auto, overflow: task.overflow,
  })
  if (result === "stop") break
  continue
}
```

`SessionCompaction.process()` summarizes the older messages into a compact summary, replaces them, and the loop continues with the shortened context.

Cross-reference: Chapter 28 covers the compaction system in detail.

---

## 18.6 Step Counting and Max Steps

```typescript
const maxSteps = agent.steps ?? Infinity
const isLastStep = step >= maxSteps
```

If the model reaches the max step count, a `MAX_STEPS` prompt is injected:

```
"You are running out of steps. Please wrap up your work and provide
a final response summarizing what you accomplished."
```

This prevents runaway loops and gives the model a chance to summarize before being cut off.

---

## 18.7 Title Generation

On the first step, `ensureTitle()` fires an async title generation task:

```typescript
if (isFirstStep) {
  ensureTitle({
    sessionID, messageID: lastUser.id,
    text: userText, model, abort,
  })
}
```

This uses the `title` agent (a lightweight prompt) to generate a 3-5 word title for the conversation. It runs in the background and updates the session title via `Session.setTitle()` -- it should never block the main loop.

---

## 18.8 Worked Example: The Blog Prompt

For our NextJS blog prompt, the loop typically executes 15-30 iterations:

**Steps 1-3: Research** -- Model calls `webfetch` (reads Next.js docs), `glob` (checks current directory), emits reasoning about its plan. Each step: finish reason `tool-calls` -> loop continues.

**Steps 4-6: Scaffolding** -- Model calls `bash` (`npx create-next-app@latest`), permission check fires, command runs. Then `bash` (`npm install gray-matter remark`), `write` (creates markdown posts).

**Steps 7-15: Building** -- Model alternates between `read` (inspect scaffolding), `edit` (modify pages/components), and `write` (create new files). Each iteration: tool-call -> tool-result -> finish-step with cost tracking.

**Steps 16-20+: Verification** -- Model calls `bash` (`npm run build`). If build fails: reads error, calls `edit` to fix, calls `bash` again. The verify-fix-verify cycle repeats until the build succeeds.

**Exit** -- On the final text-only response, `finish === "stop"` -> loop breaks. Session status set to "idle", SSE event published, CLI exits.

---

## 18.9 Agent Resolution

Before each step, the loop resolves which agent is active. The agent determines the model, permissions, prompt, and tool set:

```typescript
const agent = await Agent.get(resolvedAgentName)
const permission = PermissionNext.merge(agent.permission, sessionPermission, approved)
```

### Built-In Agents

| Agent | Mode | Purpose | Key Permissions |
|-------|------|---------|----------------|
| `build` | primary | Default agent. Edits files, runs commands. | All tools allowed, question + plan_enter enabled |
| `plan` | primary | Research and planning only. | Edit tools **denied** (except plan `.md` files) |
| `general` | subagent | Multi-step tasks via TaskTool. | Todo tools denied (prevents state leaks between parent/child) |
| `explore` | subagent | Fast codebase exploration. | Only read-only tools: grep, glob, list, read, bash, webfetch |
| `title` | hidden | Generates 3-5 word session titles. | All tools denied (text generation only) |
| `compaction` | hidden | Summarizes long conversations. | All tools denied |
| `summary` | hidden | Generates session summaries. | All tools denied |

### Agent Switching

The `plan_exit` tool enables agent transitions. When invoked:
1. The tool asks the user to confirm switching (via `Question.ask()`)
2. If confirmed, a synthetic user message is injected with `agent: "build"`
3. The loop picks up the new agent on the next iteration

This creates a plan → build workflow: the `plan` agent researches and writes a plan file, then `plan_exit` switches to `build` which executes the plan.

---

## 18.10 Tool Resolution Pipeline

Each loop iteration resolves the available tools through a 4-step pipeline:

```
ToolRegistry.tools(model, agent)
    |
    |  1. Built-in tools (22 defined)
    |  2. Filter by model (apply_patch only for GPT-5+)
    |  3. Filter by feature flags (LSP, batch, plan, websearch)
    |
    v
resolveTools()
    |
    |  4. Agent permission filtering (disabled tools removed)
    |  5. MCP tools added (namespaced: {server}_{tool})
    |  6. Plugin hooks (tool.definition, tool.register)
    |  7. Wrap each tool for AI SDK integration
    |
    v
streamText({ tools })
```

The result is a `Record<string, AITool>` where each key is a tool name and each value wraps `execute()` with permission checks, output truncation, and session state updates.

---

## 18.11 Inter-Step Data Flow

The data flow between the loop and processor on each iteration:

```
┌─── LOOP ITERATION ───────────────────────────┐
│                                               │
│  1. Load messages (filterCompacted)           │
│  2. Resolve agent, model, tools               │
│  3. Build system prompt                       │
│  4. Create fresh Processor                    │
│                                               │
│  ┌─── PROCESSOR ──────────────────────────┐   │
│  │                                         │   │
│  │  stream = LLM.stream(messages, tools)   │   │
│  │  for await (event of stream.fullStream) │   │
│  │    text-delta  → Bus.publish(PartDelta) │   │
│  │    tool-call   → execute + updatePart   │   │
│  │    finish-step → snapshot + cost        │   │
│  │                                         │   │
│  │  return "continue" | "compact" | "stop" │   │
│  └─────────────────────────────────────────┘   │
│                                               │
│  "continue" → goto 1 (re-read messages)      │
│  "compact"  → SessionCompaction.process()     │
│  "stop"     → break                          │
│                                               │
└───────────────────────────────────────────────┘
```

The key insight is that the processor's return value controls the loop. The processor is stateless between iterations -- a new one is created each time, with fresh `toolcalls`, `snapshot`, and `blocked` state.

---

## Source File Map

| Concept | File |
|---------|------|
| Main loop | `session/prompt.ts` (`SessionPrompt.loop()`) |
| Agent definitions | `agent/agent.ts` |
| Tool resolution | `session/prompt.ts` (`resolveTools()`) |
| Tool registry | `tool/registry.ts` |
| Compaction | `session/compaction.ts` |
| Summary | `session/summary.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/compaction.test.ts` | 423 | Compaction trigger detection, summary generation, compacted message filtering |
| `test/session/revert-compact.test.ts` | 286 | Reverting to pre-compaction state |
| `test/session/prompt.test.ts` | 212 | Prompt creation and variant resolution that precedes loop entry |
| `test/tool/registry.test.ts` | 122 | Tool discovery, filtering by model/agent, custom tool loading |
