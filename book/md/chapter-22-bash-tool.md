# Chapter 22: The Bash Tool -- Command Execution and Permission Parsing

> *"With great power comes great need for permission checks."*

---

## 22.1 Overview

The bash tool (`tool/bash.ts`, ~270 lines) is one of the most complex tools because it bridges the gap between the AI's intent and actual shell command execution. It must balance power (the model needs to run arbitrary commands) with safety (the user must approve destructive operations).

---

## 22.2 Parameters

```typescript
parameters: z.object({
  command: z.string().describe("The command to execute"),
  timeout: z.number().describe("Optional timeout in milliseconds").optional(),
  workdir: z.string().describe("Working directory. Use this instead of 'cd'.").optional(),
  description: z.string().describe("Clear, concise description in 5-10 words"),
})
```

The `description` parameter is notable -- the model must describe what the command does in plain English. This serves double duty: it becomes the tool call's title in the TUI, and it gives the user context when reviewing permission requests.

The `workdir` parameter replaces `cd` commands. This is a deliberate design choice: `cd` in a subprocess doesn't persist, so a `workdir` parameter is more reliable.

---

## 22.3 Command Parsing with Tree-sitter

Before executing, the bash tool parses the command using Tree-sitter's Bash grammar:

```typescript
const parser = lazy(async () => {
  const { Parser } = await import("web-tree-sitter")
  // Load tree-sitter-bash WASM module
  const p = new Parser()
  p.setLanguage(bashLanguage)
  return p
})

// In execute():
const tree = await parser().then((p) => p.parse(params.command))
```

Tree-sitter parsing enables:
1. **Command extraction** -- identifies individual commands within a pipeline
2. **Argument analysis** -- finds paths in commands like `rm`, `cp`, `mv`
3. **Arity-based permission matching** -- extracts the command name and subcommands for permission rules

---

## 22.4 Permission via Arity Matching

The tool extracts permission patterns from the parsed AST:

```typescript
for (const node of tree.rootNode.descendantsOfType("command")) {
  const command = []
  for (let i = 0; i < node.childCount; i++) {
    const child = node.child(i)
    if (child.type === "command_name" || child.type === "word" || ...)
      command.push(child.text)
  }
  patterns.add(commandText)
  always.add(BashArity.prefix(command).join(" ") + " *")
}
```

`BashArity.prefix()` extracts the significant prefix of a command for permission matching. For example:
- `npm install gray-matter` -> arity prefix `npm install *` (user can "always allow" any `npm install`)
- `git commit -m "..."` -> arity prefix `git commit *`
- `ls -la` -> arity prefix `ls *`

This lets users grant blanket permissions like "always allow `npm install *`" without approving every individual package.

---

## 22.5 External Directory Detection

Before execution, the tool checks if the command touches files outside the project:

```typescript
if (["cd", "rm", "cp", "mv", "mkdir", "touch", "chmod", "chown", "cat"].includes(command[0])) {
  for (const arg of command.slice(1)) {
    if (arg.startsWith("-")) continue
    const resolved = await fs.realpath(path.resolve(cwd, arg))
    if (!Instance.containsPath(resolved)) {
      directories.add(dir)
    }
  }
}

if (directories.size > 0) {
  await ctx.ask({ permission: "external_directory", patterns: globs, ... })
}
```

If the command references paths outside the project root, a separate `external_directory` permission is required. This prevents the agent from accidentally modifying system files.

---

## 22.6 Process Spawning

The command runs in a child process:

```typescript
const proc = spawn(params.command, {
  shell,          // detected via Shell.acceptable()
  cwd,            // workdir or project directory
  env: { ...process.env, ...shellEnv.env },
  stdio: ["ignore", "pipe", "pipe"],
  detached: process.platform !== "win32",
})
```

The `detached: true` flag (on Unix) creates a process group, enabling clean kill of the process and all its children via `Shell.killTree()`.

---

## 22.7 Output Streaming

Output is captured and streamed to the TUI in real-time:

```typescript
proc.stdout?.on("data", append)
proc.stderr?.on("data", append)

const append = (chunk: Buffer) => {
  output += chunk.toString()
  ctx.metadata({
    metadata: {
      output: output.length > MAX_METADATA_LENGTH
        ? output.slice(0, MAX_METADATA_LENGTH) + "\n\n..."
        : output,
      description: params.description,
    },
  })
}
```

The `ctx.metadata()` callback updates the TUI on every chunk. The metadata output is capped at `MAX_METADATA_LENGTH` (30KB) to prevent the TUI from slowing down, but the full output is returned to the LLM.

---

## 22.8 Timeout and Abort

```
DEFAULT_TIMEOUT = OPENCODE_EXPERIMENTAL_BASH_DEFAULT_TIMEOUT_MS || 2 minutes
```

Two cancellation mechanisms:
- **Timeout** -- `setTimeout` kills the process tree after the configured timeout
- **Abort** -- user cancellation via AbortSignal kills the process immediately

Both append metadata to the output: `<bash_metadata>bash tool terminated command after exceeding timeout</bash_metadata>`.

---

## 22.9 Security: Process Isolation and Shell Safety

### Shell Blacklisting

Not all shells can be used safely. Fish and Nushell are blacklisted because their syntax is incompatible with POSIX command parsing (Tree-sitter's Bash grammar can't parse them):

```typescript
const BLACKLIST = new Set(["fish", "nu"])
export const acceptable = lazy(() => {
  const s = process.env.SHELL
  if (s && !BLACKLIST.has(path.basename(s))) return s
  return fallback()  // bash, zsh, or sh
})
```

If the user's default shell is blacklisted, the bash tool falls back to `bash`, `zsh`, or `/bin/sh`.

### Detached Process Groups and Tree Cleanup

Commands are spawned with `detached: true` on Unix, which creates a new process group. This enables `killTree()` to terminate the command AND all its children:

```typescript
Shell.killTree(proc) {
  process.kill(-pid, "SIGTERM")     // Negative PID = kill entire process group
  await sleep(200)                   // 200ms grace period
  if (!exited()) process.kill(-pid, "SIGKILL")  // Force kill if still running
}
```

On Windows, the equivalent uses `taskkill /pid {pid} /f /t` (force kill tree). This prevents zombie processes from commands that spawn sub-processes (e.g., `npm run dev` spawning a Node server).

### No OS-Level Sandbox

> [!IMPORTANT]
> OpenCode does **NOT** run commands in a container, chroot, or OS-level sandbox. The user's shell has full access to the system.

Security relies entirely on the permission system: every command must be approved by the user (or match a previously approved pattern). This is a deliberate design trade-off:

- **Pro**: Commands work exactly as they would in a regular terminal (no path translation, no filesystem mounts, no network isolation surprises)
- **Con**: A malicious or confused model with blanket permissions could modify system files

The arity-based permission system (§22.4) mitigates this by letting users approve categories (`npm install *`) rather than blanket shell access.

---

## Source File Map

| Concept | File |
|---------|------|
| Bash tool | `tool/bash.ts` |
| Shell detection | `shell/shell.ts` |
| Arity matching | `permission/arity.ts` |
| Tool description | `tool/bash.txt` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/tool/bash.test.ts` | 403 | Command execution, timeout, abort, output capture |
| `test/permission/arity.test.ts` | 33 | Arity prefix extraction for bash commands |
| `test/tool/external-directory.test.ts` | 128 | External directory permission checks |
