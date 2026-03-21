# Chapter 24: The Task Tool — Spawning Sub-Agents

---

## Notes & Key Points

### 24.1 TaskTool (`tool/task.ts`)
- Creates a child session with a different agent
- The model can delegate work to `explore`, `general`, or custom sub-agents
- ~5.5KB implementation
- Each subtask gets its own message history and tool context
- Results flow back to the parent session as tool output

### 24.2 Subtask Lifecycle

1. Model calls `task` tool with: `{ prompt, description, subagent_type }`
2. The tool creates a child session (`Session.create({ parentID })`)
3. Sends the prompt to the child session's agent
4. Waits for the child session's loop to complete
5. Returns the assistant's response as tool output

### 24.3 BatchTool (`tool/batch.ts`)
- Experimental tool for executing multiple tool calls in parallel
- Enabled via `experimental.batch_tool` config

---

## Source File Map

| Tool | File |
|------|------|
| Task | `tool/task.ts` |
| Prompt | `tool/task.txt` |
| Batch | `tool/batch.ts` |

---

## 🧪 Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/tool/task.test.ts` | 45 | Basic task tool invocation, child session creation |
| `test/permission-task.test.ts` | 319 | Permission handling for task tools — how sub-agent permissions interact with parent session permissions |
