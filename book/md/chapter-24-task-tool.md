# Chapter 24: The Task Tool -- Spawning Sub-Agents

> *"When one agent isn't enough, spawn another."*

---

## 24.1 What the Task Tool Does

The task tool (`tool/task.ts`, ~170 lines) is OpenCode's mechanism for delegating work to sub-agents. When the primary agent encounters a task that's better handled by a specialist (research, exploration, focused implementation), it calls the task tool to spawn a child session with a different agent.

---

## 24.2 Parameters

```typescript
const parameters = z.object({
  description: z.string().describe("A short (3-5 words) description"),
  prompt: z.string().describe("The task for the agent to perform"),
  subagent_type: z.string().describe("The type of specialized agent"),
  task_id: z.string().describe("Resume a previous task").optional(),
  command: z.string()
    .describe("The command that triggered this task")
    .optional(),
})
```

The `task_id` field enables task resumption -- if the model passes a previous session's ID, the task continues in that existing session rather than creating a new one.

---

## 24.3 Agent Selection

During `init()`, the task tool builds a list of available sub-agents:

```typescript
const agents = await Agent.list().then(x => x.filter(a => a.mode !== "primary"))
const accessibleAgents = caller
  ? agents.filter(
      a => PermissionNext.evaluate(
        "task", a.name, caller.permission).action !== "deny")
  : agents
```

Only non-primary agents are available as sub-agents. Agents are filtered by the caller's permissions -- if the `plan` agent is denied the `task` permission, it can't spawn sub-agents.

The agent list is embedded in the tool's description, so the model knows which sub-agents are available and what each one does.

---

## 24.4 Child Session Creation

```typescript
const session = await Session.create({
  parentID: ctx.sessionID,
  title: params.description + ` (@${agent.name} subagent)`,
  permission: [
    { permission: "todowrite", pattern: "*", action: "deny" },
    { permission: "todoread", pattern: "*", action: "deny" },
    // Prevent recursive task spawning unless the agent explicitly allows it
    ...(hasTaskPermission ? []
      : [{ permission: "task", pattern: "*", action: "deny" }]),
  ],
})
```

Child sessions:
- Have `parentID` linking to the parent session
- Default to denying `todowrite`/`todoread` (task management tools for external systems)
- Block recursive task spawning unless the sub-agent explicitly has task permission
- Inherit the parent's model unless the sub-agent specifies its own

---

## 24.5 Execution Flow

```
Parent Loop                            Child Session
    |                                      |
    +-- TaskTool.execute() ------->  Session.create(parentID)
    |                                      |
    |                                SessionPrompt.prompt()
    |                                      |
    |                                  loop() runs autonomously
    |                                  (own model, own tools)
    |                                      |
    +-- result = text <---------  loop() returns final message
    |
    +-- continue parent loop
```

The task tool calls `SessionPrompt.prompt()` on the child session and `await`s the result. The child session runs its own agentic loop completely independently -- with its own model, tools, and permissions.

The result is wrapped in XML tags for the parent model:

```typescript
const output = [
  `task_id: ${session.id} (for resuming to continue this task if needed)`,
  "",
  "<task_result>",
  text,
  "</task_result>",
].join("\n")
```

---

## 24.6 Abort Propagation

```typescript
function cancel() { SessionPrompt.cancel(session.id) }
ctx.abort.addEventListener("abort", cancel)
using _ = defer(() => ctx.abort.removeEventListener("abort", cancel))
```

If the parent session is aborted (user presses Ctrl-C), the child session is also cancelled via `SessionPrompt.cancel()`. The `using` declaration with `defer()` ensures cleanup even if the execution throws.

---

## 24.7 Permission Checks

The task tool asks for permission before spawning (unless the call came from user-initiated `@agent` or `/command` syntax, checked via `ctx.extra?.bypassAgentCheck`):

```typescript
if (!ctx.extra?.bypassAgentCheck) {
  await ctx.ask({
    permission: "task",
    patterns: [params.subagent_type],
    always: ["*"],
  })
}
```

Cross-reference: Chapter 25 covers the permission system. Chapter 12 covers parent-child session relationships.

---

## Source File Map

| Concept | File |
|---------|------|
| Task tool | `tool/task.ts` |
| Task description | `tool/task.txt` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/tool/task.test.ts` | 45 | Child session creation, agent selection, abort propagation |
