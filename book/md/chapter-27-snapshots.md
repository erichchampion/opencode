# Chapter 27: Snapshots and Revert — Tracking File Changes

---

## Notes & Key Points

### 27.1 Snapshot System

The `Snapshot` module tracks file changes via git:
- `Snapshot.track()` — captures current state (stashes uncommitted changes, returns a snapshot ID)
- `Snapshot.patch(id)` — computes diff since snapshot
- Used at step boundaries in the processor

### 27.2 Revert Support

`SessionRevert` enables undoing agent changes:
- Stores patch data as `PatchPart` in session messages
- Can revert to a specific step in the conversation
- Uses git operations to restore file state

---

## Source File Map

| Concept | File |
|---------|------|
| Snapshot | `snapshot/index.ts`, `snapshot/service.ts` |
| Revert | `session/revert.ts` |

---

## 🧪 Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/snapshot/snapshot.test.ts` | 1,214 | **One of the most detailed tests in the project.** Git-based snapshot creation, diff generation, file change tracking, snapshot comparison, revert to previous state, edge cases with binary files, renames, and deletions |
| `test/session/revert-compact.test.ts` | 286 | Reverting past a compaction boundary — ensuring snapshot integrity across compaction events |
