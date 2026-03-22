# Chapter 3: Technology Stack and Key Dependencies

> *"Choose your tools wisely -- they shape the code you write."*

---

## Introduction

OpenCode's technology choices reflect its design principles: performance (Bun), type safety (TypeScript + Zod), provider neutrality (Vercel AI SDK), and API-first design (Hono). This chapter surveys the major dependencies and explains why each was chosen.

### What You'll Learn

- Why Bun instead of Node.js
- The role of the Vercel AI SDK as the model abstraction layer
- Hono as the HTTP server framework
- Drizzle ORM for SQLite persistence
- Zod for runtime validation
- Other notable dependencies (Effect, remeda, yargs, fuzzysort)

---

## Notes & Key Points

### 3.1 Runtime: Bun

- **Minimum version**: Bun >= 1.3.10 (specified in `package.json` as `"packageManager": "bun@1.3.10"`)
- Bun is used as both runtime and package manager (`bun.lock`, `bunfig.toml`)
- Enables `Bun.serve()` for HTTP, `Bun.file()` for filesystem, `Bun.stdin` for input
- `Bun.spawn` used for child process management
- TypeScript executed directly -- no compile step needed
- Dev command: `bun run --cwd packages/opencode src/index.ts`

**Workspace dependency resolution** -- the monorepo uses Bun's `catalog:` protocol to share dependency versions across packages. Instead of duplicating version strings, each package references the catalog:

```json
// packages/opencode/package.json
{
  "dependencies": {
    "ai": "catalog:",
    "zod": "catalog:"
  }
}

// root package.json defines the actual versions:
{
  "catalog": {
    "ai": "^5.0.0",
    "zod": "^3.23.0"
  }
}
```

This ensures all packages use the same version of shared dependencies.

### 3.2 Vercel AI SDK (`ai` package, v5)

**Version note**: OpenCode uses AI SDK v5 (the `ai` package). This is a major version with breaking changes from v4 -- notably, the `tool()` helper, structured output via `experimental_output`, and the `wrapLanguageModel()` middleware API are all v5 features.

This is the most consequential dependency. It provides:
- `streamText()` -- the core function that streams LLM responses with tool call support
- `tool()` / `jsonSchema()` -- tool definition helpers
- `wrapLanguageModel()` -- middleware for transforming model params
- Provider adapters: `@ai-sdk/anthropic`, `@ai-sdk/openai`, `@ai-sdk/google`, etc.
- `ProviderMetadata` typing for provider-specific response data

**File**: `session/llm.ts` -- the `LLM.stream()` function wraps `streamText()` with:
- System prompt injection
- Temperature/topP/topK configuration
- Tool resolution and permission filtering
- Provider-specific options merging
- Telemetry metadata

### 3.3 Hono (HTTP Framework)

- Lightweight, fast HTTP framework: `const app = new Hono()`
- OpenAPI spec generation via `hono-openapi`
- Route modules: `SessionRoutes`, `ProviderRoutes`, `EventRoutes`, etc.
- Middleware: CORS, basic auth, workspace resolution, request logging
- WebSocket support via `hono/bun` for SSE events

**File**: `server/server.ts`

### 3.4 Drizzle ORM + SQLite

- Schema-first ORM with snake_case column conventions
- Tables: `SessionTable`, `MessageTable`, `PartTable`, `ProjectTable`
- Database operations via `Database.use()` wrapper
- Migration system: `JsonMigration.run()` for first-time setup

**Files**: `storage/db.ts`, `session/session.sql.ts`, `project/project.sql.ts`

### 3.5 Zod (v4)

- Used extensively for runtime validation and type inference
- Schema definitions double as API documentation via `z.meta({ ref: ... })`
- `z.toJSONSchema()` converts Zod schemas to JSON Schema for tool parameters
- The `fn()` helper wraps functions with input validation

### 3.6 Other Notable Dependencies

| Dependency | Purpose |
|-----------|---------|
| `yargs` | CLI argument parsing |
| `remeda` | Functional utilities (pipe, sortBy, mergeDeep, pickBy) |
| `Effect` | Used in specific subsystems (VCS, LSP) for typed effect handling |
| `fuzzysort` | Fuzzy matching for model name resolution |
| `ulid` | Time-sortable unique IDs for messages/sessions |
| `marked` | Markdown rendering |
| `decimal.js` | Precise cost calculations |

### 3.7 Deep Dive: The `wrapLanguageModel` Middleware Pattern

One of the most sophisticated uses of the AI SDK is the `wrapLanguageModel()` middleware in `session/llm.ts`. This is a higher-order function that wraps a language model with transformation logic, similar to HTTP middleware:

```typescript
// Simplified from session/llm.ts
const model = wrapLanguageModel({
  model: provider.languageModel(modelID),
  middleware: {
    transformParams: async ({ params }) => {
      // Modify parameters before they reach the model
      // e.g., inject provider-specific options, adjust temperature
      return { ...params, ...providerSpecificOptions }
    },
  },
})
```

**Why this matters:** OpenCode supports 20+ providers, each with different parameter names, capabilities, and quirks. Rather than maintaining 20 separate code paths, `wrapLanguageModel` lets the codebase apply per-provider transformations as middleware -- a clean separation between "what OpenCode wants to do" and "how each provider expects it."

The `ProviderTransform` module (`provider/transform.ts`) provides the transformation logic:
- `ProviderTransform.options()` -- adjusts model-level options (temperature, max tokens, stop sequences)
- `ProviderTransform.message()` -- transforms message content per-provider (e.g., image encoding, tool call format)
- `ProviderTransform.providerOptions()` -- injects provider-specific headers, API versions, or feature flags

This pattern is tested extensively in `test/provider/transform.test.ts` (2,655 lines) which covers every supported provider.

### 3.8 Why Hono Over Express or Fastify?

OpenCode's HTTP layer uses [Hono](https://hono.dev), a relatively new framework. Here's why:

| Feature | Express | Fastify | **Hono** |
|---------|---------|---------|----------|
| Edge/Bun support | Adapter needed | Adapter needed | **Native** |
| TypeScript-first | No (DefinitelyTyped) | Partial | **Yes** |
| OpenAPI generation | Manual (swagger-jsdoc) | Plugin | **Built-in** (hono-openapi) |
| Bundle size | ~200KB | ~350KB | **~14KB** |
| Request validation | Express-validator | Ajv | **Zod integration** (@hono/zod-validator) |

The key advantage for OpenCode: **Hono runs natively on Bun** without adapter shims. Since OpenCode uses `Bun.serve()` as its HTTP runtime, Hono integrates seamlessly. The `hono-openapi` package also generates the OpenAPI spec that drives SDK generation -- one framework handles both the API server and the SDK contract.

### 3.9 The `catalog:` Workspace Dependency Resolution

(See also Chapter 2, S2.5 for context.)

The `catalog:` syntax is specifically a Bun workspace feature. When Bun resolves `"ai": "catalog:"` in a child package:

1. Bun reads the root `package.json`'s `workspaces.catalog` section
2. It finds `"ai": "5.0.124"` there
3. It resolves the dependency as if the child had written `"ai": "5.0.124"`

This is different from `workspace:*` (which points to a local package) -- `catalog:` is for external npm dependencies where you want version consistency. The root `package.json` acts as a single source of truth for version pins, making upgrades atomic: change one line in the catalog and every package picks up the new version.

---

## Source File Map

| Dependency | Usage Entry Point |
|-----------|-------------------|
| Vercel AI SDK | `session/llm.ts`, `provider/provider.ts` |
| Hono | `server/server.ts` |
| Drizzle | `storage/db.ts` |
| Zod | Throughout; `config/config.ts`, `session/schema.ts` |
| yargs | `src/index.ts` |
