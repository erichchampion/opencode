# Chapter 30: Plugins -- Extending OpenCode at Runtime

> *"Everything is a hook."*

---

## 30.1 Overview

The plugin system (`plugin/index.ts`) provides hooks at key points in OpenCode's execution. Plugins are JavaScript/TypeScript files that register callbacks for specific events, enabling customization without modifying core code.

---

## 30.2 Plugin Loading

Plugins are loaded from `.opencode/plugins/` or specified in `opencode.json`:

```json
{
  "plugins": [
    "./plugins/my-plugin.ts",
    "https://example.com/plugin.js"
  ]
}
```

Each plugin exports a function that receives a registration API:

```typescript
export default (api) => {
  api.hook("chat.params", async (ctx, params) => {
    // Modify LLM parameters before the call
    params.temperature = 0.2
    return params
  })
}
```

---

## 30.3 Available Hooks

`Plugin.trigger()` fires a named hook and lets plugins transform the data:

| Hook | Fires When | Can Modify |
|------|-----------|------------|
| `chat.params` | Before LLM call | temperature, topP, options |
| `chat.headers` | Before LLM call | HTTP headers |
| `experimental.chat.system.transform` | System prompt assembly | System prompt array |
| `experimental.text.complete` | Text part finalized | Output text |
| `tool.execute.before` | Before tool runs | Tool arguments |
| `tool.execute.after` | After tool runs | Tool result |
| `tool.register` | Tool discovery | Tool set |
| `shell.env` | Before bash execution | Environment variables |

### The Trigger Pattern

```typescript
const params = await Plugin.trigger(
  "chat.params",                    // hook name
  { sessionID, agent, model },      // context (read-only)
  { temperature: 0.7, topP: 1.0 }, // data (mutable)
)
```

Each registered callback receives the context and data, can modify the data, and the final modified version is returned. Multiple callbacks chain -- the output of one becomes the input of the next.

---

## 30.4 Custom Tools via Plugins

Plugins can register custom tools:

```typescript
api.hook("tool.register", async (ctx, tools) => {
  tools["my-tool"] = Tool.define("my-tool", {
    description: "My custom tool",
    parameters: z.object({ input: z.string() }),
    async execute(args, ctx) {
      return { title: "Result", output: "...", metadata: {} }
    },
  })
  return tools
})
```

These tools appear alongside built-in tools and are subject to the same permission system.

---

## 30.5 Security: Trusted Code Model

> [!CAUTION]
> Plugins run in the same Node.js process as OpenCode with **no sandboxing**. A malicious plugin has full access to the filesystem, network, and environment variables.

### Attack Surface Through Hooks

Plugins can modify security-critical data:
- **`chat.headers`** -- could inject or exfiltrate auth tokens
- **`chat.params`** -- could redirect API calls to a different endpoint
- **`experimental.chat.system.transform`** -- could inject prompt injection into the system prompt
- **`tool.execute.before`** / **`tool.execute.after`** -- could modify tool arguments or results
- **`shell.env`** -- could inject malicious environment variables into bash commands

### URL-Loaded Plugins

Plugins loaded from URLs (`https://example.com/plugin.js`) are fetched over HTTP:
- **No integrity checking** -- there's no hash verification or signature validation
- **MITM risk** -- non-HTTPS URLs are vulnerable to man-in-the-middle attacks
- **No versioning** -- the URL could serve different code over time

### Recommendations

1. Only use plugins from trusted sources (your own code, verified repos)
2. Pin URL-based plugins to specific commits or versions when possible
3. Review plugin source code before adding to your project
4. Prefer local plugins (`.opencode/plugins/`) over URL-based ones

---

## Source File Map

| Concept | File |
|---------|------|
| Plugin system | `plugin/index.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/plugin/plugin.test.ts` | varies | Plugin loading, hook registration, trigger chain, custom tools |
