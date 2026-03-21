# Chapter 8: The Provider Abstraction — One Interface, Twenty Backends

> *"The best abstraction makes the impossible feel inevitable."*

---

## Introduction

OpenCode is radically provider-agnostic — it can talk to Anthropic, OpenAI, Google, Amazon Bedrock, Azure, local Ollama instances, and a dozen more. This chapter explains how the provider layer achieves this through the Vercel AI SDK's provider abstraction.

### What You'll Learn

- The `Provider` namespace and model registry
- How providers are discovered, loaded, and configured
- The `BUNDLED_PROVIDERS` map and `CUSTOM_LOADERS` pattern
- The `Provider.Model` schema — capabilities, costs, limits
- The `models.dev` data source for model metadata

---

## Notes & Key Points

### 8.1 Bundled Providers

`provider/provider.ts` defines `BUNDLED_PROVIDERS` — a map from npm package names to factory functions:

```typescript
const BUNDLED_PROVIDERS = {
  "@ai-sdk/anthropic": createAnthropic,
  "@ai-sdk/openai": createOpenAI,
  "@ai-sdk/google": createGoogleGenerativeAI,
  "@ai-sdk/amazon-bedrock": createAmazonBedrock,
  // ... 20+ more
}
```

Each factory returns a Vercel AI SDK `Provider` instance.

### 8.2 Custom Loaders

For providers needing special handling, `CUSTOM_LOADERS` defines per-provider initialization logic:

- **opencode**: handles free-tier models (removes paid models if no API key)
- **openai**: uses `sdk.responses()` API
- **amazon-bedrock**: complex region detection, credential chain, cross-region inference prefix logic
- **google-vertex**: Google Auth integration, custom fetch with OAuth tokens
- **gitlab**: workflow model discovery, agentic chat integration
- **azure**: resource name resolution, Cognitive Services endpoint support

### 8.3 The Provider.Model Schema

Rich model metadata:
- `id`, `providerID`, `name`, `family`
- `capabilities`: temperature support, reasoning, attachments, tool calling, I/O modalities
- `cost`: input/output token pricing, cache read/write pricing
- `limit`: context window size, max output tokens
- `variants`: provider-specific reasoning effort levels (e.g., "high", "max")
- `headers`: custom HTTP headers for the model
- `options`: provider-specific configuration

### 8.4 Model Resolution

`Provider.getModel(providerID, modelID)` looks up a model:
1. Check in-memory cache
2. Resolve from `models.dev` data or config overrides
3. Apply custom loader transformations
4. Return a fully typed `Provider.Model`

`Provider.getLanguage(model)` converts a `Model` to a Vercel AI SDK `LanguageModel` ready for `streamText()`.

---

## Source File Map

| Concept | File |
|---------|------|
| Provider namespace | `provider/provider.ts` |
| Provider transform | `provider/transform.ts` |
| Model schemas | `provider/schema.ts` |
| Models.dev data | `provider/models.ts` |
| Auth service | `provider/auth-service.ts` |

---

## 🧪 Test References

Provider handling has the most complex test suite in the project:

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/provider/provider.test.ts` | 2,284 | Model resolution, `Provider.getModel()`, fuzzy matching, config overrides, default model fallback, model capability detection, cost/limit metadata |
| `test/provider/transform.test.ts` | 2,655 | `ProviderTransform.options()`, `ProviderTransform.message()`, `ProviderTransform.providerOptions()` — per-provider message/options transformation for every supported provider |
| `test/provider/amazon-bedrock.test.ts` | 447 | AWS credential chain, region detection, cross-region inference prefixes, profile selection |
| `test/provider/copilot/convert-to-copilot-messages.test.ts` | 523 | Message format conversion for GitHub Copilot integration |
| `test/provider/copilot/copilot-chat-model.test.ts` | 592 | Copilot chat model streaming and tool calling |
| `test/provider/gitlab-duo.test.ts` | 408 | GitLab Duo workflow models, agent chat, authentication |

---

### 8.5 Adding a New Provider: A Walkthrough

To understand the provider abstraction, let's trace what it would take to add a hypothetical new provider:

**Step 1: Add the AI SDK adapter**

```bash
bun add @ai-sdk/newprovider
```

The Vercel AI SDK provides adapter packages for each provider. If no adapter exists, you can use `@ai-sdk/openai-compatible` for any OpenAI-compatible API.

**Step 2: Register in `BUNDLED_PROVIDERS`**

```typescript
// provider/provider.ts
const BUNDLED_PROVIDERS = {
  // ... existing providers
  "@ai-sdk/newprovider": createNewProvider,
}
```

This maps the npm package name to the SDK factory function.

**Step 3: Add model metadata**

Model metadata comes from models.dev (`provider/models.ts`). If your provider isn't listed, you can define models in config:

```json
{
  "provider": {
    "newprovider": {
      "models": {
        "model-v1": {
          "name": "Model V1",
          "max_tokens": 4096,
          "context_window": 128000
        }
      }
    }
  }
}
```

**Step 4: Add a custom loader (optional)**

If the provider needs special initialization — custom auth, region detection, non-standard endpoints — add it to `CUSTOM_LOADERS`:

```typescript
const CUSTOM_LOADERS = {
  "newprovider": async (options) => {
    // Custom initialization logic
    return createNewProvider({ apiKey: options.apiKey, baseURL: options.baseUrl })
  },
}
```

**Step 5: Add transform rules (if needed)**

If the provider has message format quirks (e.g., different image encoding, incompatible tool call schemas), add cases in `provider/transform.ts`.

That's it — the rest of the system (agents, sessions, tools) works automatically because it only interacts with the AI SDK's `LanguageModel` interface.

### 8.6 The SSE Timeout Wrapper

LLM API calls can hang — network issues, provider outages, or extremely long generations. The `wrapSSE()` utility addresses this:

```typescript
// When streaming from providers, the response is wrapped with a timeout
// that fires if no data arrives within a configurable window (default: 60s)
```

The wrapper:
1. Starts a timer when the stream opens
2. Resets the timer every time data arrives
3. If the timer fires (no data for N seconds), it aborts the connection with a timeout error
4. The timeout error is classified as retryable by `SessionRetry.retryable()`

This prevents sessions from getting stuck indefinitely when a provider stops sending data mid-stream — a real-world issue with many LLM APIs.

### 8.7 The `ProviderTransform` Layer

The `ProviderTransform` module (`provider/transform.ts`, ~33K) is the provider compatibility layer. It handles the reality that every provider has its own quirks:

| Transform | What It Does | Example |
|-----------|-------------|---------|
| `options()` | Builds provider-specific model options | Anthropic uses `max_tokens` (required), OpenAI uses `max_completion_tokens` |
| `message()` | Transforms message content | Some providers don't support `image_url` in tool results; transform to text |
| `providerOptions()` | Injects provider-specific headers/config | Anthropic: `anthropic-beta` header for extended thinking; Bedrock: `guardrailConfig` |
| `maxOutputTokens()` | Provider-specific output limits | Some providers cap at 4K, others at 128K |
| `temperature()` | Default temperature per provider | Reasoning models often require temperature=1.0 |

**Example: Anthropic cache control**

```typescript
// For Anthropic, the transform adds cache_control headers to long messages
// This enables prompt caching, reducing costs by ~90% for repeated tool calls
case "anthropic":
  return {
    anthropic: {
      cacheControl: { type: "ephemeral" },
      thinking: model.capabilities?.reasoning ? { type: "enabled" } : undefined,
    },
  }
```

The key design principle: **application code never knows which provider it's talking to.** All provider differences are handled in `ProviderTransform`, keeping `session/llm.ts` and the rest of the codebase provider-agnostic.

---

## Questions for Expansion

- [x] Walk through adding a new provider
- [x] Detail the SSE timeout wrapper (`wrapSSE()`)
- [x] Explain the `ProviderTransform` message/options transformation layer
