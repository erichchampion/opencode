# Chapter 25: The Permission System -- Rules, Requests, and Approvals

> *"Trust, but verify."*

---

## 25.1 Overview

OpenCode's permission system controls which tools can execute and with what arguments. It uses a rule-based evaluation model with three possible outcomes: **allow**, **deny**, or **ask** (prompt the user). The system is implemented in `permission/service.ts` (~280 lines) using Effect's service pattern.

---

## 25.2 Rules and Rulesets

Permissions are expressed as rules:

```typescript
export const Rule = z.object({
  // tool name or category (e.g., "bash", "edit", "external_directory")
  permission: z.string(),
  // wildcard pattern to match against (e.g., "npm install *")
  pattern: z.string(),
  // "allow" | "deny" | "ask"
  action: Action,
})
export const Ruleset = Rule.array()
```

Rules come from multiple sources:
1. **Agent permissions** -- defined per-agent (e.g., `plan` agent denies `edit`)
2. **Session permissions** -- set via `Session.setPermission()` or per-prompt tool overrides
3. **Approved rules** -- accumulated during the session from user "always allow" responses
4. **Config permissions** -- from `opencode.json`'s `permission` field

---

## 25.3 Rule Evaluation

`Permission.evaluate()` determines the action for a given permission and pattern:

```typescript
export function evaluate(
  permission: string, pattern: string,
  ...rulesets: Ruleset[]): Rule {
  return evalRule(permission, pattern, ...rulesets)
}
```

The evaluation uses the `evaluate.ts` module which processes rules with wildcard matching (`Wildcard.match()`). Rules are evaluated last-match-wins -- the most recently added rule takes precedence. This means session-level rules override agent-level rules.

---

## 25.4 The Ask Flow

When a tool needs permission and the rules evaluate to "ask":

```
Tool.execute() --> ctx.ask() --> Permission.ask()
                                       |
                                       v
              Bus.publish(Event.Asked) --> TUI shows prompt
                                                   |
Deferred.await() <-- Permission.reply() <-- User responds
```

1. The tool calls `ctx.ask()` with a permission name, patterns, and metadata
2. `Permission.ask()` creates a `Deferred` (an Effect primitive for async completion)
3. `Event.Asked` is published, which the TUI or API receives
4. The execution blocks on `Deferred.await()`
5. When the user responds, `Permission.reply()` resolves the deferred

### Reply Types

| Reply | Effect | Stored? |
|-------|--------|---------|
| `"once"` | Allow this call | No |
| `"always"` | Allow all matching calls | Yes -- added to `approved` ruleset |
| `"reject"` | Deny this call | No -- throws `RejectedError` |

### Rejection Cascade

When the user rejects a permission, **all pending permissions for the same session** are also rejected:

```typescript
if (input.reply === "reject") {
  // Reject the specific request
  yield* Deferred.fail(existing.deferred, new RejectedError())
  // Reject all other pending requests for the same session
  for (const [id, item] of pending.entries()) {
    if (item.info.sessionID !== existing.info.sessionID) continue
    pending.delete(id)
    yield* Deferred.fail(item.deferred, new RejectedError())
  }
}
```

This prevents a cascade of permission prompts after the user has already decided to stop the agent.

### Always-Allow Cascade

Conversely, when the user says "always," all pending requests that now match the approved rules are auto-resolved:

```typescript
if (input.reply === "once") return
for (const [id, item] of pending.entries()) {
  const ok = item.info.patterns.every(
    (pattern) => evaluate(
      item.info.permission, pattern, approved).action === "allow"
  )
  if (ok) yield* Deferred.succeed(item.deferred, undefined)
}
```

---

## 25.5 Error Types

| Error | Thrown When | Effect on Loop |
|-------|-----------|----------------|
| `RejectedError` | User rejects | Processor sets `blocked = true` |
| `CorrectedError` | User rejects with feedback | Same as rejected, but includes user's message |
| `DeniedError` | Rule explicitly denies | Tool sees the rule and can self-correct |

---

## 25.6 Tool Category Grouping

Edit-related tools are grouped under a single permission category:

```typescript
const EDIT_TOOLS = ["edit", "write", "apply_patch", "multiedit"]
export function disabled(tools, ruleset): Set<string> {
  for (const tool of tools) {
    const permission = EDIT_TOOLS.includes(tool) ? "edit" : tool
    // ...
  }
}
```

Denying the `edit` permission disables all four edit-related tools at once. This is how the `plan` agent prevents file modifications.

---

## 25.7 Security Design Philosophy

The permission system embodies several security principles:

### Default-Ask

The fallback action is `"ask"`, not `"allow"`. If no rule in any ruleset matches, the user is always prompted:

```typescript
// permission/evaluate.ts
const match = rules.findLast(
  (rule) => Wildcard.match(permission, rule.permission)
    && Wildcard.match(pattern, rule.pattern),
)
return match ?? { action: "ask", permission, pattern: "*" }
```

This means a new tool or an unfamiliar command always requires explicit approval. Security is opt-out, not opt-in.

### Last-Match-Wins Evaluation

Rules are evaluated in order, with the last matching rule winning. This enables layered policy:
1. Agent defines base rules (e.g., `{ permission: "edit", pattern: "*", action: "deny" }`)
2. Session can override (e.g., `{ permission: "edit", pattern: "*.md", action: "allow" }`)
3. The session rule wins because it's later in the flattened ruleset

### Arity-Based Command Grouping

`BashArity.prefix()` extracts the significant prefix of a command for permission matching:
- `npm install gray-matter` --> `npm install *` (approve any npm install)
- `git commit -m "..."` --> `git commit *`
- `rm -rf node_modules` --> `rm *`

This lets users grant categorical approvals without approving every individual invocation.

### Persistence Scope

"Always allow" rules are stored in the project's database row and persist across sessions within the same project. However, they reset when:
- The project changes (different working directory)
- The database is cleared
- Rules are explicitly overridden in `opencode.json`

Static rules in `opencode.json` persist indefinitely and are version-controllable:

```json
{
  "permission": {
    "bash": { "npm *": "allow", "rm *": "ask" },
    "edit": "allow"
  }
}
```

---

## Source File Map

| Concept | File |
|---------|------|
| Permission service | `permission/service.ts` |
| Rule evaluation | `permission/evaluate.ts` |
| Arity matching | `permission/arity.ts` |
| Wildcard matching | `util/wildcard.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/permission/next.test.ts` | 1,032 | Rule evaluation with multiple rulesets, wildcard matching, precedence |
| `test/permission/arity.test.ts` | 33 | Arity prefix extraction for bash command permissions |
| `test/tool/external-directory.test.ts` | 128 | External directory permission flow end-to-end |
