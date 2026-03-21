# Chapter 10: Authentication and Credentials

> *"Trust, but verify."*

---

## Introduction

Each provider needs credentials — API keys, OAuth tokens, AWS credential chains, or service accounts. This chapter explains how OpenCode manages authentication across 20+ providers.

### What You'll Learn

- The `Auth` namespace and credential storage
- API key vs. OAuth authentication flows
- Provider-specific auth patterns (AWS, Google Vertex, GitLab)
- Environment variable resolution for credentials

---

## Notes & Key Points

### 10.1 Auth Storage

`Auth.get(providerID)` returns stored credentials. Types:
- `api` — API key string
- `oauth` — OAuth access/refresh tokens

### 10.2 Credential Sources (Priority Order)

1. Stored credentials via `Auth.set()`
2. Environment variables (provider-specific: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.)
3. Config file options (`provider.<id>.options.apiKey`)
4. OAuth flow (for providers supporting it)

### 10.3 Provider-Specific Auth

- **AWS Bedrock**: credential chain (`fromNodeProviderChain`), profiles, web identity tokens, bearer tokens
- **Google Vertex**: `GoogleAuth` library, application default credentials
- **GitLab**: `PRIVATE-TOKEN` header vs. `Bearer` OAuth header

---

## Source File Map

| Concept | File |
|---------|------|
| Auth module | `auth/index.ts` |
| Provider auth | `provider/auth-service.ts`, `provider/auth.ts` |
| Environment | `env/index.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/auth/auth.test.ts` | 58 | `Auth.get()`, `Auth.set()`, credential storage and retrieval per-provider |
| `test/plugin/auth-override.test.ts` | 45 | How plugins can override authentication credentials |
| `test/cli/plugin-auth-picker.test.ts` | 120 | Auth picker UI for choosing between multiple credentials |
| `test/account/service.test.ts` | 282 | Account service integration, token management, org switching |

---

### 10.4 OAuth Flow: How It Works

For providers that support OAuth (OpenAI, GitHub Copilot, GitLab Duo), OpenCode implements a browser-based OAuth flow:

```
opencode auth login openai
    |
    +-- 1. Generate PKCE challenge (code_verifier + code_challenge)
    +-- 2. Start local HTTP server on random port (callback listener)
    +-- 3. Open browser --> provider's OAuth authorization URL
    |       with client_id, redirect_uri=localhost:PORT, scope, code_challenge
    |
    |   (User logs in via browser, approves access)
    |
    +-- 4. Browser redirects to localhost:PORT/callback?code=AUTH_CODE
    +-- 5. Exchange AUTH_CODE for access_token + refresh_token
    |       via provider's token endpoint
    +-- 6. Store tokens via Auth.set("openai", { type: "oauth", ... })
    +-- 7. Close local HTTP server
```

The `test/mcp/oauth-browser.test.ts` (249 lines) tests this flow end-to-end.

### 10.5 The `opencode auth` CLI Command

The auth CLI provides several subcommands:

| Command | What It Does |
|---------|-------------|
| `opencode auth login <provider>` | Start OAuth flow or prompt for API key |
| `opencode auth logout <provider>` | Remove stored credentials |
| `opencode auth status` | Show authentication status for all providers |
| `opencode auth ls` | List all providers with their auth state |

When multiple credentials exist for a provider (e.g., API key + OAuth token), the auth picker UI lets the user choose which to use.

### 10.6 Security Considerations

Credential storage in OpenCode:

- **Where**: credentials are stored in the user's XDG data directory (`~/.local/share/opencode/` on Linux, `~/Library/Application Support/opencode/` on macOS)
- **Format**: JSON files, readable only by the owning user (file permissions `0600`)
- **Not stored**: credentials are never written to `opencode.json` or any project-level config. The `{env:VAR}` syntax in config files references environment variables at runtime rather than embedding secrets
- **Plugin overrides**: plugins can inject custom auth handlers (tested in `test/plugin/auth-override.test.ts`), but cannot access credentials from other providers
- **Process isolation**: the `OPENCODE_PID` environment variable prevents credential leakage to child processes that aren't part of the agent
