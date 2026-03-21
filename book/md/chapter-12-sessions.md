# Chapter 12: Sessions — Creating, Persisting, and Resuming Conversations

> *"Every conversation has a beginning, but a good session management system lets it have a middle too."*

---

## Notes & Key Points

### 12.1 Session Model

Sessions are the top-level unit of conversation, stored in SQLite via `SessionTable`:
- `id` — descending ULID (newest first)
- `slug` — human-readable URL-safe identifier
- `projectID` — links to the project
- `parentID` — for child sessions (sub-agent work)
- `title` — auto-generated or user-specified
- `version` — OpenCode version that created it
- `summary` — additions/deletions/files changed
- `permission` — session-level permission overrides
- Timestamps: `created`, `updated`, `compacting`, `archived`

### 12.2 Key Operations

- `Session.create()` — creates a new session with defaults
- `Session.fork()` — duplicates a session (copies messages up to a point)
- `Session.touch()` — updates the `time_updated` timestamp
- `Session.messages()` — retrieves messages with parts
- `Session.share()` / `Session.unshare()` — external sharing
- `Session.setTitle()`, `Session.setArchived()`, `Session.setPermission()`

### 12.3 Events

Sessions emit events via the Bus:
- `Session.Event.Created`, `.Updated`, `.Deleted`, `.Diff`, `.Error`

---

## Source File Map

| Concept | File |
|---------|------|
| Session namespace | `session/index.ts` |
| SQL schema | `session/session.sql.ts` |
| Schema types | `session/schema.ts` |

---

## 🧪 Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/session/session.test.ts` | 142 | `Session.create()` event emission (`Session.Event.Created`), event ordering (created before updated), step-finish token propagation via Bus events |
| `test/session/messages-pagination.test.ts` | 115 | Message pagination for large sessions |
| `test/server/session-list.test.ts` | 90 | Session listing via the HTTP API |
| `test/server/session-select.test.ts` | 78 | Session selection and retrieval via API |
| `test/server/session-messages.test.ts` | 119 | Retrieving messages for a session via API |
