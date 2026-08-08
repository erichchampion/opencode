# Chapter 27: Snapshots and Reverting -- Git-Based Change Tracking

> *"Every change the agent makes can be undone."*

---

## 27.1 Overview

The snapshot system (`snapshot/service.ts`, ~320 lines) provides fine-grained change tracking and revert support using a private Git repository. Every agentic step is bookended by `track()` and `patch()` calls that record exactly which files changed.

---

## 27.2 The Shadow Git Repository

Snapshots use a separate Git directory (not the project's `.git`):

```
$HOME/.local/share/opencode/snapshot/{projectID}/
```

This is a bare-ish Git repo initialized with `git init --git-dir`. It points at the project's worktree but has its own history. This means:
- Snapshots don't pollute the project's Git history
- The project can be in a dirty state and snapshots still work
- Snapshots can be garbage-collected independently (`gc --prune=7.days`)

---

## 27.3 track() -- Capturing State

```typescript
const track = Effect.fn("Snapshot.track")(function* () {
  if (!(yield* enabled())) return
  // Auto-init on first use
  if (!existed) {
    yield* git(
        ["init"],
        { env: { GIT_DIR: gitdir, GIT_WORK_TREE: worktree } })
  }
  yield* add()                    // git add .
  const result = yield* git(args(["write-tree"]))
  return result.text.trim()       // tree hash
})
```

`git write-tree` captures the current index as a tree object and returns its hash. This is lighter than a full commit -- no author, message, or parent chain. Just a pure snapshot of the file tree.

---

## 27.4 patch() -- Computing Changes

```typescript
const patch = Effect.fn("Snapshot.patch")(function* (hash: string) {
  yield* add()
  const result = yield* git(args(
    ["diff", "--no-ext-diff", "--name-only", hash, "--", "."]))
  return {
    hash,
    files: result.text.trim().split("\n").filter(Boolean)
      .map(x => path.join(worktree, x)),
  }
})
```

After the step completes, `patch()` diffs the current state against the pre-step snapshot. The result is a list of changed file paths plus the snapshot hash.

---

## 27.5 restore() -- Reverting to a Snapshot

```typescript
const restore = Effect.fn("Snapshot.restore")(function* (snapshot: string) {
  // set index to snapshot
  yield* git(args(["read-tree", snapshot]))
  yield* git(args(["checkout-index", "-a", "-f"])) // checkout all files
})
```

This restores the working tree to exactly the state captured in the snapshot. It's used by `SessionRevert` when the user requests a revert.

---

## 27.6 revert() -- File-Level Revert

```typescript
const revert = Effect.fn("Snapshot.revert")(
  function* (patches: Snapshot.Patch[]) {
  for (const item of patches) {
    for (const file of item.files) {
      const result = yield* git(args(["checkout", item.hash, "--", file]))
      if (result.code !== 0) {
        // File didn't exist before -- delete it
        const tree = yield* git(args(["ls-tree", item.hash, "--", rel]))
        if (!tree.text.trim()) yield* remove(file)
      }
    }
  }
})
```

`revert()` restores individual files from patches, handling both modified files (checkout from snapshot) and newly created files (delete them if they didn't exist in the snapshot).

---

## 27.7 diffFull() -- Rich Diffs

`diffFull()` computes detailed before/after content for each changed file:

```typescript
export const FileDiff = z.object({
  file: z.string(),
  before: z.string(),    // full file content before
  after: z.string(),     // full file content after
  additions: z.number(),
  deletions: z.number(),
  status: z.enum(["added", "deleted", "modified"]).optional(),
})
```

This is used by the sharing system to display rich diffs and by the session summary to compute change statistics.

---

## 27.8 Lifecycle

```
Step 1: track()     ->  snapshot hash A
        (model edits files)
        patch(A)    ->  changed files list
        StepFinishPart { snapshot: newHash }
        PatchPart { hash, files }

Step 2: track()     ->  snapshot hash B
        (model edits more files)
        patch(B)    ->  changed files list
        ...

Revert: restore(A)  ->  working tree returns to state before Step 1
```

The `StepFinishPart` and `PatchPart` records provide a complete audit trail of every file change, making full-session revert possible.

---

## 27.9 Cleanup

A background job runs hourly to garbage-collect old snapshots:

```typescript
yield* cleanup().pipe(
  Effect.repeat(Schedule.spaced(Duration.hours(1))),
  Effect.delay(Duration.minutes(1)),
  Effect.forkScoped,
)
```

---

## Source File Map

| Concept | File |
|---------|------|
| Snapshot service | `snapshot/service.ts` |
| Session revert | `session/revert.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/revert.test.ts` | 258 | Snapshot-based revert: reverting to a specific step, restoring deleted files |
| `test/session/revert-compact.test.ts` | 286 | Reverting across compaction boundaries |
| `test/patch/patch.test.ts` | 348 | Unified diff generation from snapshot patches |
