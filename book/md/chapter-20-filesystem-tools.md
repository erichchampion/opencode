# Chapter 20: File System Tools — Read, Write, Edit, and Glob

> *"An agent that can't touch the filesystem is just a chatbot."*

---

## Notes & Key Points

### 20.1 ReadTool (`tool/read.ts`)

Reads file contents with:
- Line range selection (`startLine`, `endLine`)
- Automatic line numbering in output
- Directory detection (delegates to list)
- External directory permission checks
- ~9KB implementation

### 20.2 WriteTool (`tool/write.ts`)

Creates new files:
- Permission checks for the file path
- Creates parent directories as needed
- LSP diagnostics integration (shows warnings after write)

### 20.3 EditTool (`tool/edit.ts`)

The most complex file tool (~21KB):
- Search-and-replace edits within files
- Unified diff generation for the metadata
- Multi-edit support
- Handles encoding edge cases
- LSP diagnostics after edits

### 20.4 GlobTool (`tool/glob.ts`)

Pattern-based file search:
- Uses the project's glob implementation
- Respects `.gitignore`
- Returns matched file paths with metadata

### 20.5 ListTool (`tool/ls.ts`)

Directory listing:
- Shows files with size and modification time
- Configurable depth
- Respects gitignore

### 20.6 ApplyPatchTool (`tool/apply_patch.ts`)

Alternative to edit/write for GPT-5+ models:
- Accepts unified diff format
- Applies patches to files
- Model-specific: only enabled for certain OpenAI models

### 20.7 MultiEditTool (`tool/multiedit.ts`)

Wrapper for making multiple edits in a single call.

---

## 📝 Worked Example: Building the Blog with Filesystem Tools

During our blog prompt, the filesystem tools do the heavy lifting:

**Write — Creating markdown posts and new files:**
```
write({ filePath: "posts/2024-03-15-getting-started.md", content: "---\ntitle: Getting Started\n..." })
```
The WriteTool creates parent directories (`posts/`) if needed, writes the file via `Bun.write()`, and triggers LSP diagnostics.

**Edit — Modifying the scaffolded `app/page.tsx`:**
```
edit({
  filePath: "app/page.tsx",
  old: "export default function Home() {\n  return (\n    <main>...",
  new: "import { getAllPosts } from '@/lib/posts'\n\nexport default function Home() {\n  const posts = getAllPosts()\n  return (\n    <main>..."
})
```
The EditTool finds the `old` string, replaces it, generates a unified diff (shown in the UI), and writes the file back. LSP diagnostics then check for TypeScript errors.

**Read — Inspecting scaffolded files:**
```
read({ filePath: "app/layout.tsx" })
```
Returns line-numbered content. The model uses this to understand what it's working with before editing.

**Glob — Finding project structure:**
```
glob({ pattern: "**/*.{ts,tsx}", path: "." })
```
Returns all TypeScript files, respecting `.gitignore`. The model uses this for orientation.

**Snapshot tracking:** At each step boundary, `Snapshot.track()` captures a git stash point. After the step, `Snapshot.patch()` computes the diff — producing `PatchPart` records that show exactly which files changed.

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

## 🧪 Test References

Filesystem tools have some of the most detailed test coverage:

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/tool/read.test.ts` | 505 | Line range reading, line numbering, directory detection, external directory permission checks, encoding handling, large file truncation |
| `test/tool/write.test.ts` | 349 | File creation, parent directory creation, permission checks, LSP diagnostic triggering, overwrite behavior |
| `test/tool/edit.test.ts` | 684 | Search-and-replace, multi-edit, unified diff generation, encoding edge cases, ambiguous match handling, LSP integration |
| `test/tool/apply_patch.test.ts` | 567 | Unified diff format parsing and application, multi-file patches, edge cases |
| `test/file/index.test.ts` | 852 | Underlying file operations — reading, writing, path resolution, gitignore handling |
| `test/file/path-traversal.test.ts` | 198 | Security: path traversal prevention (symlinks, `..` escapes) |
