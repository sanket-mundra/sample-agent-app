from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .models import (
    MASKED_SECRET,
    ChatMessage,
    LLMConfig,
    LLMConfigResponse,
    MCPServerConfig,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LLM_PATH = DATA_DIR / "llm_config.json"
MCP_PATH = DATA_DIR / "mcp_servers.json"
HISTORY_PATH = DATA_DIR / "chat_history.json"


def _atomic_write(path: Path, payload: Any) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=path.name + ".", dir=str(DATA_DIR))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


# ---------- LLM config ----------


def load_llm_config() -> LLMConfig:
    data = _read_json(LLM_PATH)
    if not data:
        return LLMConfig()
    try:
        return LLMConfig.model_validate(data)
    except Exception:
        return LLMConfig()


def save_llm_config(cfg: LLMConfig) -> None:
    _atomic_write(LLM_PATH, cfg.model_dump())


def mask_llm_config(cfg: LLMConfig) -> LLMConfigResponse:
    return LLMConfigResponse(
        vendor=cfg.vendor,
        model=cfg.model,
        api_key=MASKED_SECRET if cfg.api_key else "",
        temperature=cfg.temperature,
        base_url=cfg.base_url,
        system_prompt=cfg.system_prompt,
    )


def merge_llm_update(existing: LLMConfig, incoming: LLMConfig) -> LLMConfig:
    """Preserve existing api_key if the incoming value is the mask placeholder."""
    data = incoming.model_dump()
    if data.get("api_key") in ("", MASKED_SECRET):
        data["api_key"] = existing.api_key
    return LLMConfig.model_validate(data)


# ---------- MCP servers ----------


def load_mcp_servers() -> list[MCPServerConfig]:
    data = _read_json(MCP_PATH)
    if not data:
        return []
    servers: list[MCPServerConfig] = []
    for entry in data:
        try:
            servers.append(MCPServerConfig.model_validate(entry))
        except Exception:
            continue
    return servers


def save_mcp_servers(servers: list[MCPServerConfig]) -> None:
    _atomic_write(MCP_PATH, [s.model_dump() for s in servers])


def mask_mcp_servers(servers: list[MCPServerConfig]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in servers:
        d = s.model_dump()
        if d.get("headers"):
            d["headers"] = {k: MASKED_SECRET for k in d["headers"]}
        if d.get("env"):
            # env often contains tokens; mask values but keep keys visible
            d["env"] = {k: MASKED_SECRET for k in d["env"]}
        out.append(d)
    return out


def merge_mcp_update(
    existing: list[MCPServerConfig], incoming: list[MCPServerConfig]
) -> list[MCPServerConfig]:
    """For each incoming server, replace masked header/env values with the existing ones."""
    by_id = {s.id: s for s in existing}
    merged: list[MCPServerConfig] = []
    for inc in incoming:
        prev = by_id.get(inc.id)
        if prev is not None:
            new_headers = dict(inc.headers)
            for k, v in list(new_headers.items()):
                if v == MASKED_SECRET and k in prev.headers:
                    new_headers[k] = prev.headers[k]
            new_env = dict(inc.env)
            for k, v in list(new_env.items()):
                if v == MASKED_SECRET and k in prev.env:
                    new_env[k] = prev.env[k]
            inc = inc.model_copy(update={"headers": new_headers, "env": new_env})
        merged.append(inc)
    return merged


# ---------- Chat history ----------


def load_history() -> list[ChatMessage]:
    data = _read_json(HISTORY_PATH)
    if not data:
        return []
    messages: list[ChatMessage] = []
    for entry in data:
        try:
            messages.append(ChatMessage.model_validate(entry))
        except Exception:
            continue
    return messages


def save_history(messages: list[ChatMessage]) -> None:
    _atomic_write(HISTORY_PATH, [m.model_dump() for m in messages])


def append_message(message: ChatMessage) -> list[ChatMessage]:
    history = load_history()
    history.append(message)
    save_history(history)
    return history


def clear_history() -> None:
    save_history([])
