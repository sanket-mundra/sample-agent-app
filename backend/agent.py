from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Optional

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import (
    TextMessage,
    ToolCallExecutionEvent,
    ToolCallRequestEvent,
)
from autogen_core.models import ChatCompletionClient
from autogen_ext.models.anthropic import AnthropicChatCompletionClient
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.tools.mcp import (
    McpWorkbench,
    SseServerParams,
    StdioServerParams,
    StreamableHttpServerParams,
)

from .models import (
    ChatMessage,
    LLMConfig,
    MCPServerConfig,
    MCPServerStatus,
    ToolCallRecord,
)
from .observability import trace_chat_turn

logger = logging.getLogger(__name__)

AGENT_NAME = "personal_agent"
_MAX_TOOL_RESULT_PREVIEW = 800


class AgentService:
    """Owns the LLM client + MCP workbenches. Rebuilt on config changes."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._llm_config: Optional[LLMConfig] = None
        self._servers: list[MCPServerConfig] = []
        self._client: Optional[ChatCompletionClient] = None
        self._workbenches: list[McpWorkbench] = []
        self._statuses: list[MCPServerStatus] = []
        # tool_name -> server_name (for display in tool call blocks)
        self._tool_to_server: dict[str, str] = {}

    # ---------- public ----------

    @property
    def statuses(self) -> list[MCPServerStatus]:
        return list(self._statuses)

    async def rebuild(
        self, llm: LLMConfig, servers: list[MCPServerConfig]
    ) -> None:
        async with self._lock:
            await self._teardown()
            self._llm_config = llm
            self._servers = servers
            self._client = self._build_client(llm)
            await self._start_workbenches(servers)

    async def shutdown(self) -> None:
        async with self._lock:
            await self._teardown()

    async def send_message(
        self,
        user_text: str,
        history: Optional[list[ChatMessage]] = None,
    ) -> ChatMessage:
        async with self._lock:
            if self._client is None or self._llm_config is None:
                raise RuntimeError(
                    "LLM is not configured. Set a vendor/model/API key in Settings."
                )
            mcp_names = [s.name for s in self._servers if s.enabled]
            with trace_chat_turn(
                user_text=user_text,
                vendor=self._llm_config.vendor,
                model=self._llm_config.model,
                mcp_servers=mcp_names,
            ) as turn:
                try:
                    agent = AssistantAgent(
                        name=AGENT_NAME,
                        model_client=self._client,
                        workbench=self._workbenches if self._workbenches else None,
                        system_message=self._llm_config.system_prompt,
                        reflect_on_tool_use=True,
                    )
                    task = self._build_task(user_text, history or [])
                    result = await agent.run(task=task)
                    response = self._build_response_message(result.messages)
                except Exception as e:
                    turn.record_error(str(e))
                    raise
                turn.finish_llm(
                    output=response.content,
                    usage=self._extract_usage(result.messages),
                )
                for tc in response.tool_calls:
                    turn.span_tool_call(
                        server_name=tc.server_name,
                        tool_name=tc.tool_name,
                        arguments=tc.arguments,
                        result=tc.result,
                        error=tc.error,
                    )
                turn.finish_trace(output=response.content)
                return response

    def _build_task(
        self, user_text: str, history: list[ChatMessage]
    ) -> list[TextMessage]:
        """Replay prior turns as TextMessages so the model sees full context.

        AssistantAgent accepts a list of BaseChatMessage as `task`. Each entry
        is added to the model's context before it responds. We replay past
        user and assistant turns (inlining tool-call summaries into assistant
        text so the model knows what actions it already took), then append the
        new user message last.
        """
        messages: list[TextMessage] = []
        for m in history:
            if m.role == "user":
                if m.content:
                    messages.append(TextMessage(content=m.content, source="user"))
            elif m.role == "assistant":
                rendered = self._render_assistant_for_history(m)
                if rendered:
                    messages.append(
                        TextMessage(content=rendered, source=AGENT_NAME)
                    )
            # system role is handled by AssistantAgent.system_message
        messages.append(TextMessage(content=user_text, source="user"))
        return messages

    @staticmethod
    def _render_assistant_for_history(msg: ChatMessage) -> str:
        """Inline tool calls into the assistant text so history replay preserves them."""
        parts: list[str] = []
        for tc in msg.tool_calls:
            try:
                args_str = json.dumps(tc.arguments, ensure_ascii=False)
            except (TypeError, ValueError):
                args_str = str(tc.arguments)
            header = f"[tool_call] {tc.server_name}.{tc.tool_name}({args_str})"
            if tc.error:
                outcome = f"error: {tc.error}"
            elif tc.result is not None:
                preview = tc.result
                if len(preview) > _MAX_TOOL_RESULT_PREVIEW:
                    preview = preview[:_MAX_TOOL_RESULT_PREVIEW] + "…[truncated]"
                outcome = f"result: {preview}"
            else:
                outcome = "result: (none)"
            parts.append(f"{header}\n{outcome}")
        if msg.content:
            parts.append(msg.content)
        return "\n\n".join(parts).strip()

    # ---------- internals ----------

    def _build_client(self, llm: LLMConfig) -> ChatCompletionClient:
        if llm.vendor == "openai":
            kwargs: dict[str, Any] = {
                "model": llm.model,
                "api_key": llm.api_key or "missing",
                "temperature": llm.temperature,
            }
            if llm.base_url:
                kwargs["base_url"] = llm.base_url
            return OpenAIChatCompletionClient(**kwargs)
        if llm.vendor == "anthropic":
            return AnthropicChatCompletionClient(
                model=llm.model,
                api_key=llm.api_key or "missing",
                temperature=llm.temperature,
            )
        raise ValueError(f"Unknown vendor: {llm.vendor}")

    def _build_server_params(self, s: MCPServerConfig):
        if s.transport == "stdio":
            if not s.command:
                raise ValueError("stdio transport requires a command")
            return StdioServerParams(
                command=s.command,
                args=list(s.args),
                env=dict(s.env) if s.env else None,
                cwd=s.cwd,
                read_timeout_seconds=30,
            )
        if s.transport == "streamable_http":
            if not s.url:
                raise ValueError("streamable_http transport requires a url")
            return StreamableHttpServerParams(
                url=s.url,
                headers=dict(s.headers) if s.headers else None,
            )
        if s.transport == "sse":
            if not s.url:
                raise ValueError("sse transport requires a url")
            return SseServerParams(
                url=s.url,
                headers=dict(s.headers) if s.headers else None,
            )
        raise ValueError(f"Unknown transport: {s.transport}")

    async def _start_workbenches(self, servers: list[MCPServerConfig]) -> None:
        self._workbenches = []
        self._statuses = []
        self._tool_to_server = {}
        for s in servers:
            if not s.enabled:
                self._statuses.append(
                    MCPServerStatus(
                        id=s.id, name=s.name, enabled=False, connected=False
                    )
                )
                continue
            try:
                params = self._build_server_params(s)
                wb = McpWorkbench(server_params=params)
                await wb.start()
                tools = await wb.list_tools()
                for t in tools:
                    # ToolSchema is a TypedDict with "name"
                    name = t.get("name") if isinstance(t, dict) else getattr(t, "name", None)
                    if name:
                        self._tool_to_server[name] = s.name
                self._workbenches.append(wb)
                self._statuses.append(
                    MCPServerStatus(
                        id=s.id,
                        name=s.name,
                        enabled=True,
                        connected=True,
                        tool_count=len(tools),
                    )
                )
            except Exception as e:  # noqa: BLE001
                logger.exception("Failed to start MCP server %s", s.name)
                self._statuses.append(
                    MCPServerStatus(
                        id=s.id,
                        name=s.name,
                        enabled=True,
                        connected=False,
                        error=str(e),
                    )
                )

    async def _teardown(self) -> None:
        for wb in self._workbenches:
            try:
                await wb.stop()
            except Exception:  # noqa: BLE001
                logger.exception("Error stopping workbench")
        self._workbenches = []
        self._statuses = []
        self._tool_to_server = {}
        if self._client is not None:
            try:
                close = getattr(self._client, "close", None)
                if close is not None:
                    res = close()
                    if asyncio.iscoroutine(res):
                        await res
            except Exception:  # noqa: BLE001
                logger.exception("Error closing model client")
        self._client = None

    # ---------- response shaping ----------

    @staticmethod
    def _extract_usage(messages: list[Any]) -> Optional[dict[str, int]]:
        """Aggregate prompt/completion tokens from any message that carries models_usage."""
        prompt = 0
        completion = 0
        seen = False
        for m in messages:
            usage = getattr(m, "models_usage", None)
            if usage is None:
                continue
            pt = getattr(usage, "prompt_tokens", None)
            ct = getattr(usage, "completion_tokens", None)
            if pt is not None:
                prompt += int(pt)
                seen = True
            if ct is not None:
                completion += int(ct)
                seen = True
        if not seen:
            return None
        return {
            "input": prompt,
            "output": completion,
            "total": prompt + completion,
        }

    def _build_response_message(self, messages: list[Any]) -> ChatMessage:
        """Walk agent.run() output and collapse into a single assistant ChatMessage.

        We pair ToolCallRequestEvent with the matching ToolCallExecutionEvent by
        FunctionCall.id == FunctionExecutionResult.call_id, and use the last
        TextMessage from the assistant as the final content.
        """
        tool_calls: list[ToolCallRecord] = []
        pending: dict[str, ToolCallRecord] = {}
        final_text = ""

        for m in messages:
            if isinstance(m, ToolCallRequestEvent):
                for fc in m.content or []:
                    args: dict[str, Any] = {}
                    raw_args = getattr(fc, "arguments", None)
                    if isinstance(raw_args, str):
                        try:
                            args = json.loads(raw_args) if raw_args else {}
                        except json.JSONDecodeError:
                            args = {"_raw": raw_args}
                    elif isinstance(raw_args, dict):
                        args = raw_args
                    tool_name = getattr(fc, "name", "unknown")
                    record = ToolCallRecord(
                        server_name=self._tool_to_server.get(tool_name, "mcp"),
                        tool_name=tool_name,
                        arguments=args,
                    )
                    pending[getattr(fc, "id", tool_name)] = record
                    tool_calls.append(record)
            elif isinstance(m, ToolCallExecutionEvent):
                for fr in m.content or []:
                    call_id = getattr(fr, "call_id", None)
                    record = pending.get(call_id) if call_id else None
                    if record is None and tool_calls:
                        # Fallback: attach to most recent un-resolved call
                        for r in reversed(tool_calls):
                            if r.result is None and r.error is None:
                                record = r
                                break
                    if record is None:
                        continue
                    content = getattr(fr, "content", None)
                    is_error = getattr(fr, "is_error", False)
                    text = content if isinstance(content, str) else json.dumps(content, default=str)
                    if is_error:
                        record.error = text
                    else:
                        record.result = text
            elif isinstance(m, TextMessage):
                if getattr(m, "source", None) != "user":
                    final_text = m.content or final_text

        return ChatMessage(
            role="assistant",
            content=final_text,
            timestamp=time.time(),
            tool_calls=tool_calls,
        )


# module-level singleton wired up by FastAPI lifespan
agent_service = AgentService()
