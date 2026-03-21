# Chapter 29: MCP — Model Context Protocol Integration

---

## Notes & Key Points

### 29.1 What is MCP?

The Model Context Protocol (MCP) is an open standard for connecting AI systems to external tools and data sources. OpenCode supports MCP both as a client (connecting to MCP servers) and as a server (exposing its tools via MCP).

### 29.2 MCP Client

- `mcp/index.ts` — manages connections to configured MCP servers
- MCP servers defined in `opencode.json` config
- Tools from MCP servers are automatically registered in the tool registry
- Supports stdio and HTTP transport modes

### 29.3 MCP Server

- `mcp/server.ts` — exposes OpenCode's tools as an MCP server
- Allows external clients to use OpenCode's capabilities

---

## Source File Map

| Concept | File |
|---------|------|
| MCP client | `mcp/index.ts` |
| MCP server | `mcp/server.ts` |

---

## 🧪 Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/mcp/headers.test.ts` | 153 | Custom header configuration for MCP transport, header merging, per-server header overrides |
| `test/mcp/oauth-auto-connect.test.ts` | 199 | Automatic OAuth connection flow for MCP servers, token refresh, reconnection |
| `test/mcp/oauth-browser.test.ts` | 249 | Browser-based OAuth flow for MCP servers, callback handling, token storage |
