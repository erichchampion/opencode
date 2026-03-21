# Chapter 9: Loading a Model — From Config String to Language Model

> *"A model ID is just a string until you give it a voice."*

---

## Introduction

When the user specifies `--model anthropic/claude-sonnet-4-20250514` or the config sets a default model, a chain of resolution steps converts that string into a callable `LanguageModel`. This chapter traces that path.

### What You'll Learn

- `Provider.parseModel()` — splitting `providerID/modelID`
- `Provider.getModel()` — resolving metadata from models.dev
- `Provider.getLanguage()` — creating the AI SDK language model
- `Provider.defaultModel()` — fallback resolution
- The `ProviderTransform` layer — adapting options per-provider

---

## Notes & Key Points

### 9.1 Model ID Format

Models are specified as `providerID/modelID`:
- `anthropic/claude-sonnet-4-20250514`
- `openai/gpt-4o`
- `opencode/anthropic/claude-sonnet-4-20250514` (opencode proxy)

`Provider.parseModel()` splits the string and returns `{ providerID, modelID }`.

### 9.2 Resolution Chain

1. Parse the string into provider + model IDs
2. Look up provider info (npm package, base URL, env vars)
3. Look up model metadata (capabilities, costs, limits)
4. Apply config overrides and custom loader options
5. Create the SDK provider instance
6. Get the language model from the SDK

### 9.3 ProviderTransform

`provider/transform.ts` (~33K) handles per-provider message and options transformation:
- `ProviderTransform.options()` — builds provider-specific options (max tokens, caching, etc.)
- `ProviderTransform.message()` — transforms message format for specific providers
- `ProviderTransform.providerOptions()` — provider-specific options (Anthropic cache control, etc.)
- `ProviderTransform.maxOutputTokens()` — output token limits
- `ProviderTransform.temperature()` — provider-specific temperature defaults

---

## Source File Map

| Concept | File |
|---------|------|
| Model resolution | `provider/provider.ts` |
| Transform layer | `provider/transform.ts` |
| Schema definitions | `provider/schema.ts` |

---

## Test References

Model resolution is tested extensively in the provider suite:

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/provider/provider.test.ts` | 2,284 | `Provider.parseModel()`, `Provider.getModel()`, fuzzy model matching via fuzzysort, model config overrides, default model resolution, capability and cost metadata lookup |
| `test/provider/transform.test.ts` | 2,655 | `ProviderTransform.maxOutputTokens()`, `ProviderTransform.temperature()` — how model options vary per-provider |

---

### 9.4 End-to-End: Resolving `anthropic/claude-sonnet-4-20250514`

Let's trace a concrete model resolution:

```
User: --model anthropic/claude-sonnet-4-20250514
    |
    v
Provider.parseModel("anthropic/claude-sonnet-4-20250514")
    |  Returns: { providerID: "anthropic", modelID: "claude-sonnet-4-20250514" }
    v
Provider.getModel("anthropic", "claude-sonnet-4-20250514")
    |
    +-- 1. Check models.dev data for "anthropic"
    |       --> finds model entry with capabilities, cost, limits
    |
    +-- 2. Apply config overrides (if any)
    |       --> user may override temperature, max_tokens, etc.
    |
    +-- 3. Return Provider.Model:
            {
              id: "claude-sonnet-4-20250514",
              providerID: "anthropic",
              name: "Claude Sonnet 4",
              capabilities: { reasoning: true, attachments: true, toolCalling: true },
              cost: { input: 3.0, output: 15.0 },  // per million tokens
              limit: { context: 200000, output: 64000 }
            }
    v
Provider.getLanguage(model)
    |
    +-- 1. Check CUSTOM_LOADERS for "anthropic" --> none
    +-- 2. Lookup BUNDLED_PROVIDERS --> createAnthropic
    +-- 3. Call createAnthropic({ apiKey, baseURL })
    +-- 4. Return provider.languageModel("claude-sonnet-4-20250514")
           --> Vercel AI SDK LanguageModel ready for streamText()
```

### 9.5 Fuzzy Model Matching via fuzzysort

Users don't have to type exact model IDs. The `fuzzysort` library provides intelligent fuzzy matching:

```
User types: "sonnet"
    |
    v
fuzzysort.go("sonnet", allModels, { key: "id", threshold: -10000 })
    |
    +-- Matches: "claude-sonnet-4-20250514" (score: -50)
    +-- Matches: "claude-3-5-sonnet-20241022" (score: -80)
    +-- Matches: "claude-3-sonnet-20240229" (score: -100)
    |
    v
Best match: "claude-sonnet-4-20250514"
```

This is used in the TUI's model picker and in config parsing — if you write `"model": "sonnet"` in your config, it resolves to the best-matching model for any configured provider.

### 9.6 Model Overrides in Config

The config system allows per-model overrides that layer on top of the models.dev data:

```jsonc
{
  "provider": {
    "anthropic": {
      "models": {
        "claude-sonnet-4-20250514": {
          // Override the default max output tokens
          "max_tokens": 16384,
          // Override temperature
          "temperature": 0.5,
          // Add custom headers for this model
          "headers": {
            "anthropic-beta": "max-tokens-3-5-sonnet-2024-07-15"
          }
        }
      }
    }
  }
}
```

The override merge happens during `Provider.getModel()` — models.dev provides the base metadata, and config overrides layer on top. This is tested in `test/provider/provider.test.ts` with cases like "config max_tokens overrides default".
