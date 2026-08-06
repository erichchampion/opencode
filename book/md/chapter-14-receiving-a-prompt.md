# Chapter 14: Receiving a Prompt -- From User Input to the Agentic Loop

> *"Before the machine can think, it must know what to think about."*

---

## 14.1 The Entry Point

Every prompt enters through `SessionPrompt.prompt()` in `session/prompt.ts`. This function bridges the gap between user input (from the TUI, CLI, or API) and the agentic loop. It's surprisingly simple -- most of the complexity is in the setup:

```typescript
export const prompt = fn(PromptInput, async (input) => {
  const session = await Session.get(input.sessionID)
  // clear any pending revert state
  await SessionRevert.cleanup(session)
  const message = await createUserMessage(input)
  // update timestamp
  await Session.touch(input.sessionID)

  // handle backwards-compatible tool enable/disable via permissions
  const permissions: PermissionNext.Ruleset = []
  for (const [tool, enabled] of Object.entries(input.tools ?? {})) {
    permissions.push({
      permission: tool,
      action: enabled ? "allow" : "deny",
      pattern: "*",
    })
  }
  if (permissions.length > 0) {
    session.permission = permissions
    await Session.setPermission({
      sessionID: session.id, permission: permissions })
  }

  if (input.noReply === true) return message
  return loop({ sessionID: input.sessionID })
})
```

Three important things happen before the loop:
1. **Revert cleanup** -- if a previous revert was pending, `SessionRevert.cleanup()` clears it
2. **User message creation** -- `createUserMessage()` builds the `MessageV2.User` with all parts
3. **Permission setup** -- per-prompt tool overrides (`{ "bash": false }`) become session-scoped permission rules

---

## 14.2 PromptInput -- What the User Sends

The `PromptInput` schema defines everything a prompt can carry:

```typescript
export const PromptInput = z.object({
  sessionID: SessionID.zod,
  // for retrying a specific message
  messageID: MessageID.zod.optional(),
  model: z.object({
    providerID: ProviderID.zod,
    modelID: ModelID.zod,
  // override model for this prompt
  }).optional(),
  // override agent (e.g., "plan")
  agent: z.string().optional(),
  // store message but don't run loop
  noReply: z.boolean().optional(),
  // text or JSON schema output
  format: MessageV2.Format.optional(),
  // custom system prompt addition
  system: z.string().optional(),
  // reasoning effort level
  variant: z.string().optional(),
  parts: z.array(z.discriminatedUnion("type", [
    // user's text
    TextPartInput,
    // attached files (images, documents)
    FilePartInput,
    // @agent mentions
    AgentPartInput,
    // sub-task requests
    SubtaskPartInput,
  ])),
})
```

The `parts` array lets a single prompt carry mixed content: text, files, agent references, and sub-task commands. The TUI parses user input to extract `@agent` mentions and file attachments into separate parts.

### The `noReply` Flag

Setting `noReply: true` stores the user message but doesn't invoke the agentic loop. This is used by the API when callers want to batch multiple messages before triggering a response, or when injecting context without expecting a reply.

---

## 14.3 Creating the User Message

`createUserMessage()` assembles the `MessageV2.User` object:

1. **Resolve the model** -- uses the prompt's model override, falls back to the agent's default, then the session's previous model
2. **Resolve the agent** -- checks for `@agent` parts, falls back to the prompt's agent field, then the default agent
3. **Create the message** -- inserts via `Session.updateMessage()` with a `MessageID.ascending()` (ascending because messages are ordered chronologically within a session)
4. **Attach parts** -- loops through input parts, creating `TextPart`, `FilePart`, or `AgentPart` entries via `Session.updatePart()`
5. **Resolve file attachments** -- file parts with data URLs get decoded; file paths get read and encoded

### Prompt Template Resolution

`resolvePromptParts()` handles the `@file` syntax in prompts. When a user writes `@README.md` in their prompt, it:
1. Scans for `ConfigMarkdown.files()` -- recognized file references
2. Reads each file from disk
3. Creates `FilePart` entries with the file contents as data URLs

---

## 14.4 Model and Agent Resolution

The prompt-time model resolution follows a priority chain:

```
User's explicit model  -->  Agent's default model
    -->  Session's last model  -->  Config default
```

Agent resolution works similarly:
```
@agent mention in parts  -->  input.agent field
    -->  Session's last agent  -->  "coder" (default)
```

The `@agent` mention syntax (e.g., `@plan can you review this?`) is parsed from `AgentPart` entries in the parts array. This lets users switch agents mid-conversation without changing settings.

---

## 14.5 Prompt Variants (Reasoning Effort)

The `variant` field controls reasoning effort. Some models support multiple effort levels:

| Variant | Effect | Example Models |
|---------|--------|----------------|
| (none) | Default behavior | All |
| `"high"` | Extended thinking | Claude 3.5+, o3-mini |
| `"max"` | Maximum reasoning budget | Claude with extended thinking |

Variants are defined per-model in the provider configuration. The option merge chain in `LLM.stream()` applies them: `base -> model.options -> agent.options -> variant`.

---

## 14.6 Structured Output

When `format` is set to `json_schema`, the prompt system injects a `StructuredOutput` tool and a system prompt directive telling the model to call that tool with its final answer:

```
"IMPORTANT: The user has requested structured output. You MUST use the
StructuredOutput tool to provide your final response."
```

The JSON schema is validated on both sides: the Zod schema defines the expected structure, and the model's output is parsed against it with configurable retry count.

Cross-reference: Chapter 16 covers how the structured output tool integrates with `streamText()`.

---

## 14.7 The Bridge to the Loop

After message creation, `prompt()` calls `loop({ sessionID })`. This is the handoff point -- from here, control passes to the agentic loop (Chapter 18), which iterates through LLM calls and tool executions until the model produces a final response.

The `prompt()` function returns a `Promise<MessageV2.WithParts>` -- the final assistant message with all its parts. The caller (TUI, CLI, or API handler) awaits this promise while the loop runs.

---

## Source File Map

| Concept | File |
|---------|------|
| Prompt entry | `session/prompt.ts` (`SessionPrompt.prompt()`) |
| User message creation | `session/prompt.ts` (`createUserMessage()`) |
| Prompt template files | `config/markdown.ts` |
| Prompt variants | `provider/transform.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/prompt.test.ts` | 212 | Prompt creation and variant resolution that precedes loop entry |
| `test/session/structured-output.test.ts` | 386 | Structured output (JSON schema) prompt handling and tool injection |
| `test/session/structured-output-integration.test.ts` | 233 | End-to-end structured output with tool calling |
