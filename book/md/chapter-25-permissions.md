# Chapter 25: The Permission System — Allow, Ask, and Deny

---

## Notes & Key Points

### 25.1 Permission Model

Permissions control which actions tools can perform. Three outcomes:
- **allow** — proceed without asking
- **ask** — prompt the user for confirmation
- **deny** — refuse the action immediately

### 25.2 Permission Rulesets

A ruleset is an array of rules, evaluated in order:
```typescript
type Rule = {
  permission: string   // e.g., "bash", "edit", "webfetch"
  pattern: string      // glob pattern for the specific action
  action: "allow" | "ask" | "deny"
}
```

### 25.3 Permission Sources (Merge Order)

1. Agent defaults (e.g., `build` allows most things, `plan` denies writes)
2. Session-level overrides
3. User configuration overrides

### 25.4 The `ask()` Flow

When a permission is `"ask"`:
1. `PermissionNext.ask()` publishes a `Permission.Event.Asked` event
2. The session processor blocks (awaits a response)
3. The UI displays a permission prompt to the user
4. User approves or denies
5. Response published as `Permission.Event.Replied`
6. If denied, `PermissionNext.RejectedError` is thrown → tool execution fails

### 25.5 Doom Loop Protection

The processor detects when the model calls the same tool with identical args 3 times:
- Triggers a `doom_loop` permission check
- Gives the user a chance to break the cycle

---

## Source File Map

| Concept | File |
|---------|------|
| Permission service | `permission/service.ts` |
| Arity evaluation | `permission/arity.ts` |
| Schema | `permission/schema.ts` |

---

## 🧪 Test References

The permission system has exceptionally thorough test coverage — the tests essentially _are_ the tutorial for this chapter:

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/permission/next.test.ts` | 1,033 | **Comprehensive:** `fromConfig()` (string→wildcard, object→rules, tilde/`$HOME` expansion), `evaluate()` (exact/wildcard/glob matching, last-matching-rule-wins semantics, wildcard `*` permission), `merge()` (rule concatenation, config overrides defaults), `disabled()` (tool disabling when all patterns denied), `ask()` (allow/deny/ask resolution, pending promise for ask, event publishing), `reply()` (once/reject/always flows, reject-with-message → CorrectedError, reject cancels all same-session requests, always persists approval across instances) |
| `test/permission/arity.test.ts` | 33 | `BashArity.prefix()` — command token extraction for permission matching: arity-1 (unknown), arity-2 (git, docker), arity-3 (aws s3, npm run), longest-match-wins for nested prefixes |
| `test/permission-task.test.ts` | 319 | Permission interaction between parent sessions and sub-agent task tools |
