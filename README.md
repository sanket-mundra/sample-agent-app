# Sample Agent App

A minimal chat-based agentic application built on Microsoft AutoGen. FastAPI
backend + React (Vite) frontend, with MCP server support and JSON-on-disk
persistence.

## What was built

- **Chat UI** with message history, markdown-rendered assistant replies, and
  collapsible inline blocks for tool / MCP calls (showing server, tool name,
  arguments, and result).
- **LLM settings panel** — vendor (OpenAI or Anthropic), model, API key
  (password-masked), temperature, optional base URL, and editable system
  prompt. Persisted to `data/llm_config.json`.
- **MCP server panel** — add / edit / enable / remove MCP servers with
  `stdio`, `streamable_http`, or `sse` transport. Connection status surfaced
  per server. Persisted to `data/mcp_servers.json`.
- **Agent loop** — a single `AssistantAgent` wired to all enabled MCP
  workbenches. `reflect_on_tool_use=True` so the agent produces a
  natural-language final reply after tool calls.
- **Crash-safe persistence** — all JSON writes go via temp file + `os.replace`.
- **Secret masking** — `GET` responses never return raw API keys, MCP header
  values, or stdio env values; the UI sends `"***"` back on save to preserve
  unchanged secrets.

## Versions chosen (pinned)

The **`autogen-agentchat` / `autogen-ext` 0.7.x line** was picked for three
reasons: it's the actively developed modern AutoGen line (the legacy
`pyautogen` line is a different project), it has first-class MCP integration
via `McpWorkbench` + `StdioServerParams` / `StreamableHttpServerParams` /
`SseServerParams`, and the `AssistantAgent` constructor accepts a
`workbench: Workbench | Sequence[Workbench]` parameter — a clean fit for
"connect to all enabled MCP servers at chat start."

### Backend (`backend/requirements.txt`)

| Package | Version |
|---|---|
| `autogen-agentchat` | `0.7.5` |
| `autogen-ext[openai,anthropic,mcp]` | `0.7.5` |
| `fastapi` | `0.115.6` |
| `uvicorn[standard]` | `0.32.1` |
| `pydantic` | `2.10.3` |

### Frontend (`frontend/package.json`)

| Package | Version |
|---|---|
| `react`, `react-dom` | `18.3.1` |
| `react-markdown` | `9.0.1` |
| `vite` | `5.4.11` |
| `@vitejs/plugin-react` | `4.3.4` |

Tested on Python 3.13 / Node 20+.

## Install

```bash
# Backend
python3.13 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt

# Frontend
cd frontend && npm install
```

## Run (dev mode)

Two terminals:

```bash
# Terminal 1 — backend on :8000
.venv/bin/uvicorn backend.main:app --reload --port 8000
```

```bash
# Terminal 2 — frontend on :5173 (proxies /api → :8000)
cd frontend && npm run dev
```

Open http://localhost:5173.

## Adding an MCP server

Open the **MCP Servers** tab in the UI and click *Add server*.

### Example — stdio (filesystem server)

```
Name:       filesystem
Transport:  stdio
Command:    npx
Args:       -y
            @modelcontextprotocol/server-filesystem
            /Users/you/some/directory
```

(One arg per line in the textarea.)

### Example — streamable_http (remote server with auth)

```
Name:       remote-example
Transport:  streamable_http
URL:        https://mcp.example.com/v1
Headers:    Authorization: Bearer sk-abc123
```

Click *Save all*. The status badge updates to `connected · N tools` on
success, or `disconnected` with the error text if the connection fails.

## API surface

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/config/llm` | Current LLM config (API key masked). |
| `PUT` | `/api/config/llm` | Save LLM config. Send `"***"` to preserve the existing key. |
| `GET` | `/api/config/mcp` | List MCP server configs (headers/env values masked). |
| `PUT` | `/api/config/mcp` | Replace full MCP server list. Masked values are preserved. |
| `GET` | `/api/mcp/status` | Per-server connection status + tool count. |
| `GET` | `/api/chat/history` | Current chat history. |
| `POST` | `/api/chat/message` | Send a user message; returns the assistant response with any tool calls. |
| `DELETE` | `/api/chat/history` | Clear chat history. |

## Manual test checklist

1. `GET /api/health` returns `{"ok": true}`.
2. Open the UI — all three tabs render without errors before any config.
3. In **LLM Settings**, set a valid OpenAI or Anthropic key and Save. The
   key displays as `***` after save.
4. In **Chat**, send a plain "hello" — the assistant replies.
5. In **MCP Servers**, add the filesystem stdio example above. Save. Badge
   reads `connected · N tools`.
6. Back in **Chat**, ask *"list files in the shared directory"*. The
   assistant calls the tool; a collapsible block appears with server name,
   tool name, arguments, and result.
7. Add a bogus server (e.g. command `does-not-exist`). Save. Badge reads
   `disconnected` with the error text — the real server still works.
8. `DELETE /api/chat/history` (or *Clear* button) wipes history.
9. Restart backend — history, LLM config, and MCP list all load from
   `data/*.json`.

## Known limitations of the MVP

- **Single-user, local only.** No auth, no user management.
- **Plaintext API keys** on disk in `data/llm_config.json`. Acceptable for
  a local dev app; don't commit the `data/` dir (it's gitignored).
- **No streaming.** The agent returns a single response per turn. The
  architecture (`AgentService.send_message`) keeps the door open for this.
- **Single chat session.** No sidebar for multiple chats. History is one
  flat list in `data/chat_history.json`.
- **No rate limiting or request cancellation.** `/api/chat/message` calls
  are serialized with an `asyncio.Lock` so history writes don't interleave;
  users can't cancel an in-flight request from the UI.
- **Config changes rebuild all workbenches.** Saving the LLM config or the
  MCP list closes and re-opens every MCP connection. Fine for the MVP;
  finer-grained updates would be the natural next step.
- **stdio environment isolation.** MCP stdio servers inherit the backend
  process's environment, plus any `env` entries you add.

## Screenshots
<img width="893" height="1058" alt="image" src="https://github.com/user-attachments/assets/d075fc53-7972-4e83-8051-5dadbe68f7b2" />
<img width="879" height="671" alt="image" src="https://github.com/user-attachments/assets/6a7f3ec6-9ec2-4b0d-ad33-3e15b6552e75" />
<img width="877" height="851" alt="image" src="https://github.com/user-attachments/assets/bb0a8758-2f19-4e22-9e5b-7dbdc3fcd563" />
<img width="864" height="525" alt="image" src="https://github.com/user-attachments/assets/de404fb0-38aa-4e1f-a1c5-0727840188c1" />
