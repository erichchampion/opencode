# Chapter 14: Receiving a Prompt — From User Input to the Session Loop

> *"A journey of a thousand tool calls begins with a single prompt."*

---

## Notes & Key Points

### 14.1 Prompt Entry Points

A prompt can arrive via:
1. **CLI `run` command** — `opencode run "build me a blog"`
2. **TUI input** — user types in the terminal UI
3. **SDK API call** — `sdk.session.prompt({ sessionID, parts: [...] })`
4. **HTTP API** — `POST /session/:id/prompt`

All paths converge on `SessionPrompt.prompt()` in `session/prompt.ts`.

### 14.2 The PromptInput Schema

```typescript
PromptInput = z.object({
  sessionID,
  model: { providerID, modelID },  // optional override
  agent: z.string(),               // optional override
  variant: z.string(),             // reasoning effort
  format: MessageV2.Format,        // text or json_schema
  system: z.string(),              // custom system prompt
  parts: z.array(discriminatedUnion("type", [TextPart, FilePart, AgentPart, SubtaskPart]))
})
```

### 14.3 Creating the User Message

`createUserMessage(input)`:
1. Resolves attached files (reads directory listings, file contents)
2. Processes `@agent` references in text
3. Creates the user message record in the database
4. Stores file parts, text parts, agent parts

### 14.4 Entering the Loop

After creating the user message, `prompt()` calls `loop({ sessionID })`.

If the session is already processing (another prompt is in-flight), the caller gets queued — they receive a Promise that resolves when the current loop finishes.

### 14.5 The Run Command Flow

In `cli/cmd/run.ts`:
1. Parse CLI args (message, model, agent, files, session options)
2. Bootstrap the project instance
3. Create an in-process SDK client
4. Subscribe to SSE events
5. Create or resume a session
6. Call `sdk.session.prompt()` with the message
7. Loop over events, formatting tool calls and text output
8. Exit when `session.status.idle` is received

---

## 📝 Worked Example: The Blog Prompt Enters the System

Our example prompt is:

```
Use NextJS, Typescript and TailwindCSS to create a simple blog application.
The application should pull content for posts from a directory of static
markdown files, with filenames organized by date. The most recent post should
be displayed first, with subsequent posts lazy loaded as the user scrolls.
Review the documentation at https://nextjs.org/docs to ensure you use the
most recent version of the framework.
```

When the user runs `opencode run "Use NextJS..."`:

1. **CLI parses** the message via yargs → `RunCommand.handler()` fires
2. **Bootstrap** initializes the project instance (`Instance.provide()`)
3. **In-process SDK client** is created with `Server.Default().fetch` as the transport
4. **Event subscription** begins — the CLI subscribes to `message.part.updated`, `session.status`, and `permission.asked`
5. **Session created** — `sdk.session.create({})` allocates a new session ID and database row
6. **Prompt sent** — `sdk.session.prompt({ sessionID, parts: [{ type: "text", text: "Use NextJS..." }] })`
7. This hits the server route → calls `SessionPrompt.prompt()` → creates the user message → enters `loop()`

The user message is stored with:
- `model`: the default or specified model (e.g., `ollama/llama3.2`)
- `agent`: `"build"` (the default full-access agent)
- A single text part containing the prompt

From here, the loop takes over (see Chapters 15–18).

---

## Source File Map

| Concept | File |
|---------|------|
| Prompt entry | `session/prompt.ts` (`SessionPrompt.prompt()`) |
| Run command | `cli/cmd/run.ts` |
| Session routes | `server/routes/session.ts` |

---

## 🧪 Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/prompt.test.ts` | 212 | Missing file handling (graceful failure with synthetic error part), part ordering stability during async file resolution, agent variant application (only when using agent's own model), variant override via `noReply` mode |
| `test/cli/cmd/tui/prompt-part.test.ts` | 47 | Prompt part construction from TUI input |
| `test/cli/github-action.test.ts` | 198 | Prompt handling in GitHub Actions CI context |
