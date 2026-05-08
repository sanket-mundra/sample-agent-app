from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, HTTPException

from ..agent import agent_service
from ..config import append_message, clear_history, load_history
from ..models import (
    ChatMessage,
    SendMessageRequest,
    SendMessageResponse,
)

router = APIRouter(prefix="/api/chat")

# Serialize concurrent /message calls so history writes don't interleave.
_send_lock = asyncio.Lock()


@router.get("/history", response_model=list[ChatMessage])
async def get_history() -> list[ChatMessage]:
    return load_history()


@router.delete("/history")
async def delete_history() -> dict:
    clear_history()
    return {"ok": True}


@router.post("/message", response_model=SendMessageResponse)
async def post_message(req: SendMessageRequest) -> SendMessageResponse:
    text = req.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message is empty.")
    async with _send_lock:
        prior_history = load_history()
        user_msg = ChatMessage(role="user", content=text, timestamp=time.time())
        append_message(user_msg)
        try:
            reply = await agent_service.send_message(text, history=prior_history)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=502, detail=str(e))
        append_message(reply)
        return SendMessageResponse(message=reply)
