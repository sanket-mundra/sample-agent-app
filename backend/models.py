from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant with access to external tools via MCP servers. "
    "Use the available tools when they help answer the user's question. "
    "Think step by step, call tools as needed, and explain your reasoning clearly."
)

MASKED_SECRET = "***"


Vendor = Literal["openai", "anthropic"]
Transport = Literal["stdio", "streamable_http", "sse"]
Role = Literal["user", "assistant", "system"]


class LLMConfig(BaseModel):
    vendor: Vendor = "openai"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    temperature: float = 0.7
    base_url: Optional[str] = None
    system_prompt: str = DEFAULT_SYSTEM_PROMPT


class LLMConfigResponse(BaseModel):
    vendor: Vendor
    model: str
    api_key: str  # always MASKED_SECRET if a key is set, empty otherwise
    temperature: float
    base_url: Optional[str] = None
    system_prompt: str


class MCPServerConfig(BaseModel):
    id: str
    name: str
    transport: Transport
    enabled: bool = True

    # stdio
    command: Optional[str] = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: Optional[str] = None

    # http / sse
    url: Optional[str] = None
    headers: dict[str, str] = Field(default_factory=dict)


class MCPServersPayload(BaseModel):
    servers: list[MCPServerConfig]


class MCPServerStatus(BaseModel):
    id: str
    name: str
    enabled: bool
    connected: bool
    error: Optional[str] = None
    tool_count: int = 0


class ToolCallRecord(BaseModel):
    server_name: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Optional[str] = None
    error: Optional[str] = None


class ChatMessage(BaseModel):
    role: Role
    content: str = ""
    timestamp: float  # unix seconds
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    message: str


class SendMessageResponse(BaseModel):
    message: ChatMessage


class ErrorResponse(BaseModel):
    error: str


class ObservabilityConfig(BaseModel):
    enabled: bool = False
    host: str = "http://localhost:3000"
    public_key: str = ""
    secret_key: str = ""


class ObservabilityConfigResponse(BaseModel):
    enabled: bool
    host: str
    public_key: str
    secret_key: str  # MASKED_SECRET if set, empty otherwise
