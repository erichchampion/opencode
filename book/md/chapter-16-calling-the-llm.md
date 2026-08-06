# Chapter 16: Calling the LLM -- The streamText Bridge

> *"Between intent and response lies a single function call."*

---

## 16.1 Overview

`LLM.stream()` in `session/llm.ts` is the single point where OpenCode talks to any LLM. Every model, every provider, every agent -- they all go through this one function. It translates OpenCode's internal representation into the Vercel AI SDK's `streamText()` call and returns a streaming response.

The function is ~300 lines, but its conceptual flow is straightforward:

```
StreamInput --> resolve language model
            --> assemble system prompt
            --> merge options (base -> model -> agent -> variant)
            --> resolve tools (filter by permissions)
            --> call streamText()
            --> return StreamOutput
```

---

## 16.2 StreamInput -- Everything the LLM Needs

```typescript
export type StreamInput = {
  // the user message triggering this call
  user: MessageV2.User
  // context identifier
  sessionID: string
  // resolved model metadata
  model: Provider.Model
  // active agent config
  agent: Agent.Info
  // session-level permission overrides
  permission?: PermissionNext.Ruleset
  // system prompt segments
  system: string[]
  // cancellation signal
  abort: AbortSignal
  // full conversation history
  messages: ModelMessage[]
  // use small/cheap model settings
  small?: boolean
  // available tools
  tools: Record<string, Tool>
  // max retry count (default: 0)
  retries?: number
  toolChoice?: "auto" | "required" | "none"
}
```

The `small` flag is used for auxiliary operations (title generation, compaction summaries) where a cheaper, faster model is preferred.

---

## 16.3 The Option Merge Chain

Model options are built up in layers using `mergeDeep()`:

```typescript
const base = input.small
  ? ProviderTransform.smallOptions(input.model)
  : ProviderTransform.options({ model, sessionID, providerOptions })
const options = pipe(
  // provider defaults
  base,
  // model-specific overrides
  mergeDeep(input.model.options),
  // agent-specific overrides
  mergeDeep(input.agent.options),
  // variant (reasoning effort) overrides
  mergeDeep(variant),
)
```

This layered approach means:
- A provider can set baseline parameters (cache control, safety settings)
- A specific model can override them (different temperature range)
- An agent can further customize (the `plan` agent might want lower temperature)
- A variant (like `"high"` reasoning) can modify on top of everything

---

## 16.4 System Prompt Assembly

The system prompt is assembled here, combining the provider identity, user's custom system prompt, and any plugin modifications:

```typescript
system.push([
  ...(input.agent.prompt
    ? [input.agent.prompt]
    : SystemPrompt.provider(input.model)),
  ...input.system,
  ...(input.user.system ? [input.user.system] : []),
].filter(Boolean).join("\n"))
```

After assembly, the `Plugin.trigger("experimental.chat.system.transform")` hook lets plugins modify the system prompt. If the identity header is unchanged, the system is kept as a 2-part array for prompt caching optimization.

For OpenAI OAuth users, the system prompt goes into the `instructions` field instead of system messages, following that API's conventions.

---

## 16.5 Tool Resolution

`resolveTools()` filters the tool set based on permissions:

```typescript
async function resolveTools(input) {
  const disabled = PermissionNext.disabled(
    Object.keys(input.tools),
    PermissionNext.merge(
        input.agent.permission, input.permission ?? []),
  )
  for (const tool of Object.keys(input.tools)) {
    if (input.user.tools?.[tool] === false || disabled.has(tool))
      delete input.tools[tool]
  }
  return input.tools
}
```

Three sources can disable a tool:
1. **Agent permissions** -- the `plan` agent denies `edit`, `write`, and `bash`
2. **Session permissions** -- set via `Session.setPermission()`
3. **Per-prompt overrides** -- `input.user.tools` from the `PromptInput`

---

## 16.6 The LiteLLM _noop Workaround

LiteLLM proxies (and some Anthropic gateways) validate that if the message history contains tool calls, the `tools` parameter must be non-empty. This causes errors when the agent has used tools in previous turns but no tools are needed in the current turn:

```typescript
const isLiteLLMProxy = provider.options?.["litellmProxy"] === true ||
  input.model.providerID.toLowerCase().includes("litellm")

if (isLiteLLMProxy && Object.keys(tools).length === 0
    && hasToolCalls(input.messages)) {
  tools["_noop"] = tool({
    description: "Placeholder for LiteLLM proxy compatibility",
    inputSchema: jsonSchema({ type: "object", properties: {} }),
    execute: async () => ({ output: "", title: "", metadata: {} }),
  })
}
```

The `_noop` tool is never called by the model -- it's purely to satisfy the proxy's validation.

---

## 16.7 Tool Call Repair

`experimental_repairToolCall` handles models that get tool names wrong:

```typescript
async experimental_repairToolCall(failed) {
  const lower = failed.toolCall.toolName.toLowerCase()
  if (lower !== failed.toolCall.toolName && tools[lower]) {
    // Model called "Read" but tool is "read" -- auto-correct
    return { ...failed.toolCall, toolName: lower }
  }
  // Truly unknown tool -- route to the "invalid" tool
  return {
    ...failed.toolCall,
    input: JSON.stringify({
      tool: failed.toolCall.toolName,
      error: failed.error.message }),
    toolName: "invalid",
  }
}
```

The first case (case mismatch) is common with some models that capitalize tool names. The second case routes to the `invalid` tool (Chapter 19), which returns an error message telling the model the tool doesn't exist and listing available tools.

---

## 16.8 Model Middleware

The language model is wrapped with middleware that transforms messages per-provider:

```typescript
model: wrapLanguageModel({
  model: language,
  middleware: [{
    async transformParams(args) {
      if (args.type === "stream") {
        args.params.prompt = ProviderTransform.message(
            args.params.prompt, input.model, options)
      }
      return args.params
    },
  }],
})
```

`ProviderTransform.message()` handles provider-specific quirks:
- Anthropic requires tool results to have specific format
- Some providers need cache control headers on messages
- Others need reasoning parts stripped or restructured

Cross-reference: Chapter 8 covers the full `ProviderTransform` system.

---

## 16.9 The streamText() Call

The final call assembles everything:

```typescript
return streamText({
  model: wrappedModel,
  messages: [...systemMessages, ...inputMessages],
  tools,
  temperature, topP, topK,
  maxOutputTokens,
  maxRetries: input.retries ?? 0,
  abortSignal: input.abort,
  providerOptions: ProviderTransform.providerOptions(
      input.model, options),
  headers: { ...opencodeHeaders, ...modelHeaders, ...pluginHeaders },
  experimental_telemetry: { isEnabled: cfg.experimental?.openTelemetry },
})
```

The return value is a `StreamTextResult` -- an async iterable of stream events that the processor (Chapter 17) will consume.

---

## 16.10 API Key Security

OpenCode supports three authentication types per provider:

| Type | Schema | Use Case |
|------|--------|----------|
| `oauth` | Refresh token, access token, expiry | OpenCode-hosted providers with OAuth flow |
| `api` | Raw API key string | Direct provider API keys (OpenAI, Anthropic, etc.) |
| `wellknown` | Key + token pair | Platform-specific token formats |

### Local-Only Storage

API keys are stored locally in the OpenCode data directory (never sent to OpenCode servers). The `Auth.get(providerID)` function loads credentials at LLM call time.

### Auth Error Classification

If authentication fails, the error is classified as `AuthError`, which is **not retryable**. This prevents the loop from repeatedly calling the API with invalid credentials.

### Provider-Scoped Headers

OpenCode-specific headers (`x-opencode-project`, `x-opencode-session`) are only sent to `opencode.*` provider domains, not to third-party APIs. This prevents leaking project metadata to external services.

---

## Source File Map

| Concept | File |
|---------|------|
| LLM bridge | `session/llm.ts` |
| Provider transform | `provider/transform.ts` |
| Tool resolution | `session/llm.ts` (`resolveTools()`) |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/llm.test.ts` | 759 | LLM stream setup, tool resolution, provider-specific options, `experimental_repairToolCall`, `wrapLanguageModel` middleware, message construction, abort signal handling |
| `test/provider/transform.test.ts` | 2,655 | `ProviderTransform.options()`, `ProviderTransform.message()`, `ProviderTransform.providerOptions()` -- the per-provider transformation layer |
