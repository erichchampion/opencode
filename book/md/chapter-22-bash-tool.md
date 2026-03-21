# Chapter 22: Shell Execution — The Bash Tool

---

## Notes & Key Points

### 22.1 BashTool (`tool/bash.ts`)
- Executes shell commands via Bun's process spawning
- ~9KB implementation with extensive edge case handling
- Permission checks before execution
- Output capture (stdout + stderr combined)
- Timeout handling
- Working directory awareness
- Environment variable passthrough
- The prompt template (`bash.txt`, ~9.6KB) provides extensive guidance to the model about safe shell usage

### 22.2 Shell Environment (`shell/shell.ts`)
- Detects user's shell (bash, zsh, fish)
- Handles shell profile sourcing for proper PATH

---

## 📝 Worked Example: Scaffolding and Verification via Bash

The bash tool is called multiple times during our blog prompt:

**Scaffolding:**
```
bash({ command: "npx create-next-app@latest ./blog --typescript --tailwind --app --no-git --use-npm" })
```
1. `ctx.ask({ permission: "bash", patterns: ["npx create-next-app*"] })` — permission check (the `build` agent defaults to `ask` for bash)
2. User approves → `Bun.spawn()` executes the command
3. Output streamed to the part's metadata via `ctx.metadata({ title: "npx create-next-app..." })`
4. Process exits with code 0 → result returned to the model

**Dependency installation:**
```
bash({ command: "npm install gray-matter remark remark-html" })
```

**Verification — the build-test loop:**
```
bash({ command: "npm run build" })
```
- If exit code ≠ 0, the error output (stderr) becomes the tool result
- The model reads the error, identifies the issue, uses `edit` to fix it, then calls `bash` again
- This loop continues until `npm run build` succeeds

---

## Source File Map

| Tool | File |
|------|------|
| Bash | `tool/bash.ts` |
| Prompt | `tool/bash.txt` |
| Shell env | `shell/shell.ts` |

---

## 🧪 Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/tool/bash.test.ts` | 403 | Command execution, output capture (stdout+stderr), timeout handling, exit code checking, permission flows, environment passthrough, working directory behavior |
| `test/permission/arity.test.ts` | 33 | `BashArity.prefix()` — command prefix extraction for permission matching (e.g., `git checkout main` → `["git", "checkout"]`) |
| `test/util/which.test.ts` | 100 | Binary lookup on PATH — used to find shell executables |
| `test/util/process.test.ts` | 128 | Process spawning utilities underlying the bash tool |
