# Chapter 29: MCP -- Connecting External Tool Servers

> *"The Model Context Protocol turns any server into a tool provider."*

---

## 29.1 Overview

The Model Context Protocol (MCP) is an open standard for connecting AI systems with external tools and data sources. OpenCode's MCP client (`mcp/index.ts`, ~980 lines) connects to MCP servers and exposes their tools alongside OpenCode's built-in tools.

---

## 29.2 Server Types

OpenCode supports two connection modes:

### Local (stdio)

```json
{
  "mcp": {
    "my-server": {
      "type": "local",
      "command": ["node", "server.js"],
      "environment": { "API_KEY": "..." }
    }
  }
}
```

The server is spawned as a child process. Communication happens over stdin/stdout using JSON-RPC. OpenCode manages the process lifecycle -- starting it on init and killing the entire process tree on shutdown.

### Remote (HTTP)

```json
{
  "mcp": {
    "my-server": {
      "type": "remote",
      "url": "https://my-mcp-server.com/mcp",
      "headers": { "Authorization": "Bearer ..." }
    }
  }
}
```

OpenCode tries StreamableHTTP first, then falls back to SSE transport. Remote servers support OAuth authentication with auto-discovery, dynamic client registration, and browser-based authorization flows.

---

## 29.3 Connection Lifecycle

```typescript
const state = Instance.state(async () => {
  const config = cfg.mcp ?? {}
  const clients: Record<string, MCPClient> = {}
  const status: Record<string, Status> = {}

  await Promise.all(
    Object.entries(config).map(async ([key, mcp]) => {
      const result = await create(key, mcp)
      status[key] = result.status
      if (result.mcpClient) clients[key] = result.mcpClient
    })
  )
  return { status, clients }
})
```

All MCP servers are connected in parallel at startup. Each server can be in one of five states:

| Status | Meaning |
|--------|---------|
| `connected` | Ready to use |
| `disabled` | Explicitly disabled in config |
| `failed` | Connection failed (with error message) |
| `needs_auth` | OAuth required |
| `needs_client_registration` | OAuth client ID must be configured |

---

## 29.4 Tool Conversion

MCP tools are converted to Vercel AI SDK `Tool` objects:

```typescript
async function convertMcpTool(mcpTool, client, timeout): Promise<Tool> {
  return dynamicTool({
    description: mcpTool.description ?? "",
    inputSchema: jsonSchema(schema),
    execute: async (args) => {
      return client.callTool(
        { name: mcpTool.name, arguments: args },
        CallToolResultSchema,
        { resetTimeoutOnProgress: true, timeout },
      )
    },
  })
}
```

Tool names are namespaced: `{serverName}_{toolName}` (e.g., `github_create_issue`). This prevents collisions between servers that might define tools with the same name.

---

## 29.5 Resources and Prompts

Beyond tools, MCP servers can also provide:
- **Resources** -- data sources the model can read (e.g., database tables, API endpoints)
- **Prompts** -- pre-built prompt templates that map to commands

OpenCode fetches and caches these on connection and exposes them through the API.

---

## 29.6 OAuth Authentication

Remote servers can require OAuth:

1. OpenCode detects `UnauthorizedError` during connection
2. Sets status to `needs_auth` and shows a TUI toast
3. User runs `opencode mcp auth {name}` which:
   - Starts a local callback server (`McpOAuthCallback`)
   - Opens the browser with the authorization URL
   - Receives the callback with the auth code
   - Exchanges code for tokens and reconnects

---

## 29.7 Process Cleanup

On shutdown, OpenCode kills the full descendant tree of each local MCP server:

```typescript
async (state) => {
  for (const client of Object.values(state.clients)) {
    const pid = (client.transport as any)?.pid
    for (const dpid of await descendants(pid)) {
      process.kill(dpid, "SIGTERM")
    }
  }
  await Promise.all(Object.values(state.clients).map(c => c.close()))
}
```

This prevents orphaned processes from MCP servers that spawn child processes (e.g., Chrome for browser-automation tools).

---

## 29.8 Security Considerations

### Local Servers Run with Full System Access

Local MCP servers inherit the OpenCode process's environment and permissions. They are not sandboxed -- a malicious or compromised MCP server could access any file on the system.

> [!WARNING]
> Only use MCP servers from trusted sources. Local servers have the same access as OpenCode itself.

### Tool Namespacing

MCP tool names are prefixed with the server name: `{server}_{tool}` (e.g., `github_create_issue`). This prevents a malicious MCP server from overriding built-in tools like `bash` or `edit`.

### OAuth PKCE Flow

Remote servers use OAuth with PKCE (Proof Key for Code Exchange):
1. A cryptographically secure state parameter is generated via `crypto.getRandomValues()`
2. The authorization URL is opened in the user's browser
3. A local callback server (`McpOAuthCallback`) receives the redirect
4. The auth code is exchanged for tokens

This prevents CSRF attacks and ensures the callback can't be intercepted.

### Process Tree Cleanup

On shutdown, OpenCode walks the descendant tree of each local MCP server process and sends SIGTERM to every child. This prevents orphaned processes (e.g., a browser-automation server that spawns Chrome).

### Config-Based Disable

Servers can be disabled in config (`enabled: false`), which prevents them from connecting at startup. This is the recommended way to temporarily disable a server without removing its configuration.

---

## Source File Map

| Concept | File |
|---------|------|
| MCP client | `mcp/index.ts` |
| OAuth provider | `mcp/oauth-provider.ts` |
| OAuth callback | `mcp/oauth-callback.ts` |
| Auth storage | `mcp/auth.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/mcp/mcp.test.ts` | varies | MCP server connection, tool discovery, tool execution, disconnect/reconnect |
