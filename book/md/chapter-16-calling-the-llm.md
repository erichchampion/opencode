# Chapter 16: Calling the LLM — The `streamText` Bridge

> *"Between intent and response lies a single function call."*

---

## Notes & Key Points

### 16.1 The LLM.stream() Function

`session/llm.ts` contains the critical bridge between OpenCode and the Vercel AI SDK:

```typescript
export async function stream(input: StreamInput) {
  // 1. Get language model
  const language = await Provider.getLanguage(input.model)
  
  // 2. Build system prompt array
  // 3. Merge options: base → model → agent → variant
  // 4. Resolve tools (filter by permissions)
  // 5. Call streamText()
  
  return streamText({
    model: wrapLanguageModel({ model: language, middleware: [...] }),
    messages: [...systemMessages, ...inputMessages],
    tools,
    temperature, topP, topK,
    maxOutputTokens,
    abortSignal: input.abort,
    providerOptions: ProviderTransform.providerOptions(...),
    // ...
  })
}
```

### 16.2 StreamInput

| Field | Type | Purpose |
|-------|------|---------|
| `user` | `MessageV2.User` | The user message triggering this call |
| `sessionID` | `string` | Context identifier |
| `model` | `Provider.Model` | Resolved model metadata |
| `agent` | `Agent.Info` | Active agent config |
| `permission` | `Ruleset` | Session-level permission overrides |
| `system` | `string[]` | System prompt segments |
| `abort` | `AbortSignal` | Cancellation signal |
| `messages` | `ModelMessage[]` | Full conversation history |
| `tools` | `Record<string, Tool>` | Available tools |

### 16.3 Tool Resolution

`resolveTools()` filters tools based on permissions:
- Agent permissions (e.g., `plan` agent denies `edit`)
- Session-level permissions
- User-specified tool overrides

### 16.4 Model Middleware

`wrapLanguageModel()` adds middleware that:
- Calls `ProviderTransform.message()` to adapt message format per-provider
- Handles provider-specific message transformations

### 16.5 LiteLLM Compatibility

If the provider is a LiteLLM proxy and the message history contains tool calls but no active tools, a dummy `_noop` tool is injected to prevent validation errors.

### 16.6 Tool Call Repair

`experimental_repairToolCall` handles cases where the model calls a tool with the wrong case:
- If the model calls `Read` but the tool is `read`, it auto-corrects
- If truly invalid, routes to the `invalid` tool which returns an error message

---

## Source File Map

| Concept | File |
|---------|------|
| LLM bridge | `session/llm.ts` |
| Provider transform | `provider/transform.ts` |

---

## 🧪 Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/llm.test.ts` | 759 | LLM stream setup, tool resolution, provider-specific options, `experimental_repairToolCall`, `wrapLanguageModel` middleware, message construction, abort signal handling |
| `test/provider/transform.test.ts` | 2,655 | `ProviderTransform.options()`, `ProviderTransform.message()`, `ProviderTransform.providerOptions()` — the per-provider transformation layer that `LLM.stream()` depends on |
