# Chapter 20: File System Tools -- Read, Write, Edit, and Glob

> *"An agent that can't touch the filesystem is just a chatbot."*

---

## 20.1 Overview

The filesystem tools are the most-used tools in any coding session. They enable the model to read code, create files, modify existing files, and search the project. Together they form the foundation of the agent's ability to write software.

---

## 20.2 ReadTool (`tool/read.ts`, ~9KB)

Reads file contents with line range selection:

```
read({ filePath: "app/layout.tsx", startLine: 1, endLine: 50 })
```

Key behaviors:
- **Line numbering** -- output includes line numbers (e.g., `42: const foo = "bar"`) to help the model reference specific lines
- **Directory detection** -- if the path is a directory, delegates to the list tool
- **External directory checks** -- paths outside the project root trigger a permission request
- **Encoding handling** -- binary files are detected and rejected with a message
- **Large file truncation** -- output goes through `Truncate.output()` to prevent context overflow
- **Instruction resolution** -- when reading a file, `InstructionPrompt.resolve()` checks for directory-scoped `AGENTS.md` files nearby (Chapter 15)

---

## 20.3 WriteTool (`tool/write.ts`)

Creates new files:

```
write({ filePath: "posts/2024-03-15-getting-started.md", content: "---\ntitle: Getting Started\n..." })
```

Key behaviors:
- **Parent directory creation** -- creates missing intermediate directories automatically
- **Permission checks** -- external paths require approval
- **LSP diagnostics** -- after writing, triggers an LSP diagnostics check. If the LSP reports errors, they're included in the tool output: `"Warning: 2 diagnostics found after write"`

---

## 20.4 EditTool (`tool/edit.ts`, ~21KB)

The most complex filesystem tool. Uses search-and-replace:

```
edit({
  filePath: "app/page.tsx",
  old: "export default function Home() {\n  return (\n    <main>...",
  new: "import { getAllPosts } from '@/lib/posts'\n\nexport default function Home() {\n  const posts = getAllPosts()\n  return (\n    <main>..."
})
```

### Why Search-and-Replace?

OpenCode uses search-and-replace instead of line-number-based patching or unified diffs. The rationale:

1. **Model reliability** -- LLMs are better at exact string matching than counting line numbers
2. **Conflict avoidance** -- if lines were inserted or deleted since the model last read the file, line numbers would be wrong. The old text is a robust anchor.
3. **Multi-edit support** -- multiple edits can be applied to the same file in sequence

### Key behaviors:
- **Unified diff generation** -- after applying the edit, a diff is computed and stored in metadata for the TUI
- **Ambiguous match handling** -- if the `old` text matches multiple locations, the tool asks the model to provide more context
- **Encoding preservation** -- the tool preserves the file's original encoding
- **LSP diagnostics** -- triggers TypeScript error checking after the edit

---

## 20.5 GlobTool (`tool/glob.ts`)

Pattern-based file search:

```
glob({ pattern: "**/*.{ts,tsx}", path: "." })
```

- Uses the project's `Glob.scan()` implementation
- Respects `.gitignore` patterns
- Returns matched file paths with metadata (size, modification time)

---

## 20.6 ListTool (`tool/ls.ts`)

Directory listing with configurable depth:
- Shows files with size and modification timestamp
- Respects gitignore
- Useful for the model to understand project structure before diving into specific files

---

## 20.7 ApplyPatchTool (`tool/apply_patch.ts`)

An alternative to edit/write for models that produce unified diffs:

```
apply_patch({ patch: "--- a/foo.ts\n+++ b/foo.ts\n@@ -1,3 +1,4 @@\n+import { bar } from './bar'\n ..." })
```

This tool is **model-specific** -- only enabled for GPT-5+ and certain OpenAI models. These models were trained to produce unified diff format reliably, making patch-based editing more efficient than multiple search-and-replace calls.

---

## 20.8 MultiEditTool (`tool/multiedit.ts`)

A wrapper that accepts an array of edits and applies them to a single file in sequence. This reduces round-trips for models that need to make multiple changes to the same file.

---

## 20.9 Security: Path Containment and Protected Directories

Filesystem tools enforce multiple layers of security to prevent the agent from reading or modifying files it shouldn't access.

### Path Boundary Enforcement

Every file path is checked against the project boundary via `Instance.containsPath()`:

```typescript
containsPath(filepath: string) {
  if (Filesystem.contains(Instance.directory, filepath)) return true
  // Non-git projects set worktree to "/" which would match ANY path.
  // Skip worktree check to preserve external_directory permissions.
  if (Instance.worktree === "/") return false
  return Filesystem.contains(Instance.worktree, filepath)
}
```

The check covers both the working directory and the git worktree (which may differ in monorepos). The `worktree === "/"` guard prevents non-git projects from accidentally allowing access to the entire filesystem.

### Symlink Resolution

Before boundary checks, `fs.realpath()` resolves all symlinks. This prevents attacks like:
- Creating a symlink `./safe-link -> /etc/passwd` and reading through it
- Using `../` sequences to escape the project root

### Protected Directories (macOS TCC)

`file/protected.ts` defines OS-level directories that are never scanned or watched:

- **macOS TCC directories**: `Desktop`, `Documents`, `Downloads`, `Pictures`, `Music`, `Movies`, `Public`, `Applications`, `Library` (and sensitive `Library` sub-paths like `AddressBook`, `Mail`, `Messages`, `Safari`, `Cookies`, `TCC` database)
- **macOS system directories**: `/.DocumentRevisions-V100`, `/.Spotlight-V100`, `/.Trashes`, `/.fseventsd`
- **Windows directories**: `AppData`, `Downloads`, `Desktop`, `Documents`, `Pictures`, `Music`, `Videos`, `OneDrive`

These directories are excluded from file watching, glob scanning, and directory listing to prevent triggering OS permission prompts.

### External Directory Permission Gate

When a path falls outside the project, `assertExternalDirectory()` requires explicit user approval:

```typescript
export async function assertExternalDirectory(ctx, target) {
  if (Instance.containsPath(target)) return  // inside project -- no permission needed
  const glob = path.join(parentDir, "*")
  await ctx.ask({ permission: "external_directory", patterns: [glob], always: [glob] })
}
```

This is called by read, write, edit, and bash tools before accessing any external path. The "always allow" pattern is directory-scoped: approving access to `/tmp/foo.txt` allows all files in `/tmp/*`.

---

## 20.10 Worked Example: Building the Blog

During our blog prompt, the filesystem tools do the heavy lifting:

**Write** -- creates markdown posts: `write({ filePath: "posts/2024-03-15-getting-started.md", content: "..." })`. Parent directories auto-created.

**Edit** -- modifies scaffolded `app/page.tsx`: the EditTool finds the old string, replaces it, generates a diff, triggers LSP diagnostics for TypeScript errors.

**Read** -- inspects scaffolded files: `read({ filePath: "app/layout.tsx" })`. Line-numbered output helps the model reference specific locations.

**Glob** -- finds project structure: `glob({ pattern: "**/*.{ts,tsx}" })`. Returns all TypeScript files, respecting `.gitignore`.

**Snapshot tracking** -- at each step boundary, `Snapshot.track()` captures a git stash point. After the step, `Snapshot.patch()` computes the diff, producing `PatchPart` records showing exactly which files changed.

---

## Source File Map

| Tool | File |
|------|------|
| Read | `tool/read.ts` |
| Write | `tool/write.ts` |
| Edit | `tool/edit.ts` |
| Glob | `tool/glob.ts` |
| List | `tool/ls.ts` |
| Apply Patch | `tool/apply_patch.ts` |
| Multi Edit | `tool/multiedit.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/tool/read.test.ts` | 505 | Line range reading, directory detection, external directory permissions, encoding, large file truncation |
| `test/tool/write.test.ts` | 349 | File creation, parent directory creation, permission checks, LSP diagnostics |
| `test/tool/edit.test.ts` | 684 | Search-and-replace, multi-edit, unified diff generation, ambiguous matches, LSP integration |
| `test/tool/apply_patch.test.ts` | 567 | Unified diff parsing and application, multi-file patches |
| `test/file/index.test.ts` | 852 | Underlying file operations -- reading, writing, path resolution, gitignore |
| `test/file/path-traversal.test.ts` | 198 | Security: path traversal prevention (symlinks, `..` escapes) |
