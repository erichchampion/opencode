# Chapter 32: The Headless CLI — `opencode run`

---

## Notes & Key Points

### 32.1 Purpose

`opencode run` provides non-interactive batch execution:
- Takes a prompt as an argument
- Streams tool calls and text to stdout
- Exits when the model finishes

### 32.2 Implementation (`cli/cmd/run.ts`)

Key steps:
1. Parse arguments: `--model`, `--agent`, `--continue`, `--fork`, `--file`, etc.
2. Bootstrap the project instance
3. Create in-process SDK client
4. Subscribe to events (message updates, status changes, permission requests)
5. Create/resume a session
6. Send the prompt via `sdk.session.prompt()`
7. Stream output: format tool calls, text blocks, errors
8. Exit on `session.status.idle`

### 32.3 Output Formatting

The CLI uses `UI.renderMarkdown()` for colored/formatted terminal output:
- Tool calls show name, arguments, time taken
- Text output is rendered as markdown
- Errors are highlighted
- Cost/token usage shown at the end

### 32.4 File Attachments

Files can be attached via `--file`:
- Images encoded as base64 data URLs
- Text files included as file parts
- Directories listed as directory parts

---

## Source File Map

| Concept | File |
|---------|------|
| Run command | `cli/cmd/run.ts` |
| UI helpers | `cli/ui.ts` |

---

## Test References

| Test File | Lines | What It Demonstrates |
|-----------|-------|---------------------|
| `test/cli/github-action.test.ts` | 198 | GitHub Actions integration — headless execution in CI, structured output for PR comments |
| `test/cli/github-remote.test.ts` | 80 | Remote repository detection for CI environments |
| `test/cli/import.test.ts` | 54 | Import command — importing sessions from external sources |
| `test/format/format.test.ts` | 65 | Output formatting for headless mode (markdown, JSON, plain text) |
