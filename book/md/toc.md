# Inside OpenCode: How an AI Coding Agent Works

**A Code-Level Walkthrough of Architecture, Execution, and Design**

---

## Table of Contents

### Front Matter

- [README](README.md)

---

## Part I: Orientation

[Part I Introduction](part-1-orientation.md)

1. [Chapter 1: What is OpenCode?](chapter-01-what-is-opencode.md)
2. [Chapter 2: Repository Tour — From Monorepo Root to Source Tree](chapter-02-repository-tour.md)
3. [Chapter 3: Technology Stack and Key Dependencies](chapter-03-technology-stack.md)

---

## Part II: Startup and Initialization

[Part II Introduction](part-2-startup.md)

4. [Chapter 4: CLI Entry Point — Parsing Commands with Yargs](chapter-04-cli-entry-point.md)
5. [Chapter 5: Bootstrap — Project Discovery, Database, and Instance Lifecycle](chapter-05-bootstrap.md)
6. [Chapter 6: Configuration — Loading, Merging, and Validating Settings](chapter-06-configuration.md)
7. [Chapter 7: The Server — Building an HTTP API with Hono](chapter-07-server.md)

---

## Part III: Providers and Models

[Part III Introduction](part-3-providers.md)

8. [Chapter 8: The Provider Abstraction — One Interface, Twenty Backends](chapter-08-provider-abstraction.md)
9. [Chapter 9: Loading a Model — From Config String to Language Model](chapter-09-loading-a-model.md)
10. [Chapter 10: Authentication and Credentials](chapter-10-authentication.md)

---

## Part IV: Agents and Sessions

[Part IV Introduction](part-4-agents-sessions.md)

11. [Chapter 11: Agents — Roles, Permissions, and Personalities](chapter-11-agents.md)
12. [Chapter 12: Sessions — Creating, Persisting, and Resuming Conversations](chapter-12-sessions.md)
13. [Chapter 13: Messages — The Data Model Behind Every Turn](chapter-13-messages.md)

---

## Part V: The Prompt-to-Response Loop

[Part V Introduction](part-5-prompt-loop.md)

14. [Chapter 14: Receiving a Prompt — From User Input to the Session Loop](chapter-14-receiving-a-prompt.md)
15. [Chapter 15: System Prompt Construction — Building the Model's Instructions](chapter-15-system-prompt.md)
16. [Chapter 16: Calling the LLM — The `streamText` Bridge](chapter-16-calling-the-llm.md)
17. [Chapter 17: Stream Processing — Tokens, Reasoning, and Tool Calls](chapter-17-stream-processing.md)
18. [Chapter 18: The Agentic Loop — Multi-Step Execution and Continuation](chapter-18-agentic-loop.md)

---

## Part VI: Tools — Giving the Agent Hands

[Part VI Introduction](part-6-tools.md)

19. [Chapter 19: Tool Architecture — Definition, Registry, and Execution](chapter-19-tool-architecture.md)
20. [Chapter 20: File System Tools — Read, Write, Edit, and Glob](chapter-20-filesystem-tools.md)
21. [Chapter 21: Code Intelligence — Grep, CodeSearch, and LSP](chapter-21-code-intelligence.md)
22. [Chapter 22: Shell Execution — The Bash Tool](chapter-22-bash-tool.md)
23. [Chapter 23: Web Tools — Fetch and Search](chapter-23-web-tools.md)
24. [Chapter 24: The Task Tool — Spawning Sub-Agents](chapter-24-task-tool.md)

---

## Part VII: Supporting Infrastructure

[Part VII Introduction](part-7-infrastructure.md)

25. [Chapter 25: The Permission System — Allow, Ask, and Deny](chapter-25-permissions.md)
26. [Chapter 26: The Event Bus — Decoupled Communication](chapter-26-event-bus.md)
27. [Chapter 27: Snapshots and Revert — Tracking File Changes](chapter-27-snapshots.md)
28. [Chapter 28: Context Management — Compaction, Summarization, and Token Budgets](chapter-28-context-management.md)
29. [Chapter 29: MCP — Model Context Protocol Integration](chapter-29-mcp.md)
30. [Chapter 30: The Plugin System — Extending OpenCode](chapter-30-plugins.md)

---

## Part VIII: Clients and Interfaces

[Part VIII Introduction](part-8-clients.md)

31. [Chapter 31: The Terminal UI (TUI) — Ink, Rendering, and Interaction](chapter-31-tui.md)
32. [Chapter 32: The Headless CLI — `opencode run`](chapter-32-headless-cli.md)
33. [Chapter 33: The SDK — Programmatic Access](chapter-33-sdk.md)

---

## Appendices

- [Appendix A: Configuration Reference](appendix-a-configuration.md)
- [Appendix B: Tool Reference](appendix-b-tools.md)
- [Appendix C: Provider Setup Guide](appendix-c-providers.md)
- [Appendix D: Glossary](appendix-d-glossary.md)

---

## Quick Navigation by Topic

### Getting Started
- [Chapter 1: What is OpenCode?](chapter-01-what-is-opencode.md)
- [Chapter 2: Repository Tour](chapter-02-repository-tour.md)
- [Chapter 3: Technology Stack](chapter-03-technology-stack.md)
- [Appendix A: Configuration Reference](appendix-a-configuration.md)

### Architecture & Execution Flow
- [Chapter 4: CLI Entry Point](chapter-04-cli-entry-point.md)
- [Chapter 5: Bootstrap](chapter-05-bootstrap.md)
- [Chapter 7: The Server](chapter-07-server.md)
- [Chapter 14: Receiving a Prompt](chapter-14-receiving-a-prompt.md)
- [Chapter 16: Calling the LLM](chapter-16-calling-the-llm.md)
- [Chapter 17: Stream Processing](chapter-17-stream-processing.md)
- [Chapter 18: The Agentic Loop](chapter-18-agentic-loop.md)

### AI & Model Integration
- [Chapter 8: Provider Abstraction](chapter-08-provider-abstraction.md)
- [Chapter 9: Loading a Model](chapter-09-loading-a-model.md)
- [Chapter 10: Authentication](chapter-10-authentication.md)
- [Chapter 15: System Prompt](chapter-15-system-prompt.md)
- [Appendix C: Provider Setup Guide](appendix-c-providers.md)

### Tools & Agent Capabilities
- [Chapter 19: Tool Architecture](chapter-19-tool-architecture.md)
- [Chapter 20–24: Individual Tool Chapters](chapter-20-filesystem-tools.md)
- [Appendix B: Tool Reference](appendix-b-tools.md)

### Infrastructure & Extensibility
- [Chapter 25: Permissions](chapter-25-permissions.md)
- [Chapter 28: Context Management](chapter-28-context-management.md)
- [Chapter 29: MCP](chapter-29-mcp.md)
- [Chapter 30: Plugins](chapter-30-plugins.md)

---

> **Note on the Worked Example:** Throughout Parts V and VI, chapters include a running "Worked Example" section that traces our blog-application prompt through each subsystem. Look for the 📝 icon to find these sections.

> **Note on Test References:** Chapters 5–33 include a 🧪 **Test References** section listing the relevant test files from `packages/opencode/test/`. These tests serve as executable documentation — each one demonstrates a specific behavior discussed in the chapter. Run them with `bun test <path>` from the `packages/opencode` directory.

---

*Inside OpenCode: How an AI Coding Agent Works | Complete Edition*
