from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..agent import agent_service
from ..config import (
    load_llm_config,
    load_mcp_servers,
    load_observability_config,
    mask_llm_config,
    mask_mcp_servers,
    mask_observability_config,
    merge_llm_update,
    merge_mcp_update,
    merge_observability_update,
    save_llm_config,
    save_mcp_servers,
    save_observability_config,
)
from ..models import (
    LLMConfig,
    LLMConfigResponse,
    MCPServerStatus,
    MCPServersPayload,
    ObservabilityConfig,
    ObservabilityConfigResponse,
)
from ..observability import tracer

router = APIRouter(prefix="/api")


@router.get("/config/llm", response_model=LLMConfigResponse)
async def get_llm_config() -> LLMConfigResponse:
    return mask_llm_config(load_llm_config())


@router.put("/config/llm", response_model=LLMConfigResponse)
async def put_llm_config(incoming: LLMConfig) -> LLMConfigResponse:
    existing = load_llm_config()
    merged = merge_llm_update(existing, incoming)
    save_llm_config(merged)
    try:
        await agent_service.rebuild(merged, load_mcp_servers())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Config saved, but agent rebuild failed: {e}"
        )
    return mask_llm_config(merged)


@router.get("/config/mcp")
async def get_mcp_servers() -> list[dict]:
    return mask_mcp_servers(load_mcp_servers())


@router.put("/config/mcp")
async def put_mcp_servers(payload: MCPServersPayload) -> list[dict]:
    existing = load_mcp_servers()
    merged = merge_mcp_update(existing, payload.servers)
    save_mcp_servers(merged)
    try:
        await agent_service.rebuild(load_llm_config(), merged)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Config saved, but agent rebuild failed: {e}"
        )
    return mask_mcp_servers(merged)


@router.get("/mcp/status", response_model=list[MCPServerStatus])
async def get_mcp_status() -> list[MCPServerStatus]:
    return agent_service.statuses


@router.get("/config/observability", response_model=ObservabilityConfigResponse)
async def get_observability_config() -> ObservabilityConfigResponse:
    return mask_observability_config(load_observability_config())


@router.put("/config/observability", response_model=ObservabilityConfigResponse)
async def put_observability_config(
    incoming: ObservabilityConfig,
) -> ObservabilityConfigResponse:
    existing = load_observability_config()
    merged = merge_observability_update(existing, incoming)
    save_observability_config(merged)
    try:
        tracer.configure(merged)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=400,
            detail=f"Config saved, but tracer init failed: {e}",
        )
    return mask_observability_config(merged)


@router.get("/observability/status")
async def get_observability_status() -> dict:
    return {"enabled": tracer.enabled, "host": tracer.host}
