# Build an AutoGen-based Agentic Chat Application

Build a chat-based agentic application from scratch with the architecture and requirements below. Keep the initial implementation **simple and minimal** — we will add complexity later. Prioritize a clean, working end-to-end MVP over feature completeness.

---

## Tech Stack

- **Backend:** Python with FastAPI
- **Agent Framework:** Microsoft AutoGen — pick the best version for our use case (likely `autogen-agentchat` 0.4+ since it has first-class async support, native MCP integration via `autogen-ext[mcp]`, and is the actively developed line). Document the choice and the exact pinned versions in the README.
- **Frontend:** React (use Vite for the dev server, plain JavaScript or TypeScript — your call, pick whichever keeps the setup simpler). Use a minimal UI library or plain CSS; do not pull in a heavy design system.
- **LLM Vendors (initial):** OpenAI and Anthropic only.
- **Persistence:** JSON files on disk (no database).
- **Auth:** None — single-user local app. Do not add login or user management.

---

## Functional Requirements

### 1. Chat Interface
- A standard chat UI: message history (user + agent turns), an input box, and a send button.
- Render assistant messages as markdown.
- Show tool/MCP calls inline in the conversation as collapsible blocks. Each block should display:
  - The MCP server name and tool name being called
  - The arguments passed
  - The result returned
- A single active chat session is fine for the MVP — no need for a sidebar of multiple sessions yet, but the persistence layer should not make adding that hard later.

### 2. LLM Configuration (editable from UI)
A settings panel where the user can configure:
- **Vendor:** dropdown — `openai` or `anthropic`
- **Model:** text input (e.g. `gpt-4o`, `claude-sonnet-4-5`)
- **API key / token:** password-masked text input
- **Temperature:** number input (0.0–2.0)
- **Base URL** (optional, for OpenAI-compatible endpoints)
- **System prompt:** multi-line text area, pre-populated with a sensible default for a general-purpose agentic chat assistant that uses tools when helpful. Something along the lines of: *"You are a helpful AI assistant with access to external tools via MCP servers. Use the available tools when they help answer the user's question. Think step by step, call tools as needed, and explain your reasoning clearly."*

Save button persists the config to a JSON file. Config should load on app startup.

### 3. MCP Server Configuration (editable from UI)
A separate panel for managing MCP server connections. The user can add, edit, enable/disable, and remove servers. Each server entry has:
- **Name** (user-defined label)
- **Transport type:** `stdio` or `streamable_http` (also accept `sse` if AutoGen's MCP extension supports it — check the docs)
- **For stdio:** command, args (list), env (dict, optional), cwd (optional)
- **For streamable_http / sse:** URL, headers (dict, optional, useful for auth tokens)
- **Enabled:** boolean toggle

The app should connect to all *enabled* MCP servers when a chat starts and expose their tools to the agent. Failed connections should be surfaced clearly in the UI but should not crash the app — other servers should still work.

Persist the MCP server list to a JSON file.

### 4. Agent Behavior
- Build a single AutoGen agent (e.g. `AssistantAgent` in autogen-agentchat) wired to:
  - The configured LLM client
  - The configured system prompt
  - The tools exposed by all enabled MCP servers
- The agent should run a tool-use loop: call tools as needed, feed results back, and produce a final natural-language reply.
- Stream is *not* required for the MVP — a single response per turn is fine. But keep the door open architecturally.

### 5. Persistence (JSON files on disk)
Use a `data/` directory at the project root:
- `data/llm_config.json` — the LLM settings
- `data/mcp_servers.json` — the list of MCP server configs
- `data/chat_history.json` — the message history for the current session, including tool calls and results

Write atomically (write to temp file then rename) so a crash mid-write doesn't corrupt the file. Load these at startup if they exist; otherwise start with sensible defaults.

---

## API Surface (FastAPI)

Keep the API small. Suggested endpoints:

- `GET  /api/config/llm` — return current LLM config (mask the API key in the response)
- `PUT  /api/config/llm` — update LLM config
- `GET  /api/config/mcp` — list MCP server configs
- `PUT  /api/config/mcp` — replace MCP server list (or use POST/PATCH/DELETE per item — your call, just keep it simple)
- `GET  /api/chat/history` — return current chat history
- `POST /api/chat/message` — send a user message; returns the full agent response including any tool calls made along the way
- `DELETE /api/chat/history` — clear the chat

Use Pydantic models for all request/response schemas.

---

## Project Structure (suggested)

```
project-root/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── agent.py                 # AutoGen agent setup + MCP wiring
│   ├── config.py                # Config loading/saving (JSON)
│   ├── models.py                # Pydantic schemas
│   ├── routes/
│   │   ├── config.py
│   │   └── chat.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── Chat.jsx
│   │   │   ├── LLMSettings.jsx
│   │   │   ├── MCPSettings.jsx
│   │   │   └── ToolCallBlock.jsx
│   │   └── api.js               # fetch wrappers
│   ├── package.json
│   └── vite.config.js
├── data/                        # gitignored
├── .gitignore
└── README.md
```

---

## Deliverables

1. Full working code for both backend and frontend.
2. A `README.md` with:
   - What was built and which AutoGen version was chosen (and why)
   - How to install dependencies (`pip install -r requirements.txt`, `npm install`)
   - How to run backend and frontend in dev mode
   - A short example of adding an MCP server (one stdio example, one http example)
   - Known limitations of the MVP
3. A `.gitignore` that excludes `data/`, `node_modules/`, `__pycache__/`, `.venv/`, and `.env`.
4. Sensible defaults so the app boots and shows the UI even before the user has configured anything (LLM calls will obviously fail until a key is entered — surface that error gracefully).

---

## Important Constraints

- **Do not over-engineer.** No Docker, no auth, no database, no message queue, no multi-session UI, no streaming, no observability stack. Just the MVP described above.
- **Pin dependency versions** in `requirements.txt` and `package.json` so the build is reproducible.
- **Verify against current docs.** AutoGen's MCP integration API has changed across versions — before writing the agent code, check the latest `autogen-agentchat` and `autogen-ext` docs for the correct way to wire MCP tools (e.g. `McpWorkbench`, `StdioServerParams`, `SseServerParams` / `StreamableHttpServerParams`). Use what the current stable release actually supports.
- **Handle errors gracefully.** Bad API keys, unreachable MCP servers, malformed configs — none of these should crash the backend. Return a clear error to the UI.
- **Mask secrets.** Never return raw API keys or MCP auth headers in `GET` responses; show a placeholder like `"***"` and only update them when the user submits a non-placeholder value.

---

## Process

1. First, restate your understanding of the task and the AutoGen version you plan to use, and list the exact package versions you'll pin.
2. Then propose the file-by-file plan.
3. Then implement, file by file, running the backend and a quick smoke test (e.g. `curl` against the config endpoints) before moving to the frontend.
4. End with instructions for me to run it locally and a short manual-test checklist.

Ask me a clarifying question only if something is genuinely ambiguous — otherwise make a reasonable choice, document it in the README, and keep moving.
