from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .agent import agent_service
from .config import load_llm_config, load_mcp_servers
from .routes.chat_routes import router as chat_router
from .routes.config_routes import router as config_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await agent_service.rebuild(load_llm_config(), load_mcp_servers())
    except Exception:  # noqa: BLE001
        logger.exception("Initial agent rebuild failed; continuing anyway")
    try:
        yield
    finally:
        await agent_service.shutdown()


app = FastAPI(title="Sample Agent App", lifespan=lifespan)
app.include_router(config_router)
app.include_router(chat_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True}
