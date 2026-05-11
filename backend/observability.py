"""Langfuse tracing for the agent.

Strategy: use the Langfuse Python SDK directly. It wraps an OTel tracer
internally and exposes `langfuse.trace(...) / span(...) / generation(...)`
primitives. We keep a module-level client that can be rebuilt when the
user updates credentials in the Observability panel.
"""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from .models import ObservabilityConfig

logger = logging.getLogger(__name__)


class _Tracer:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._client: Optional[Any] = None
        self._cfg: Optional[ObservabilityConfig] = None

    def configure(self, cfg: ObservabilityConfig) -> None:
        with self._lock:
            self._shutdown_locked()
            self._cfg = cfg
            if not (cfg.enabled and cfg.public_key and cfg.secret_key and cfg.host):
                return
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=cfg.public_key,
                    secret_key=cfg.secret_key,
                    host=cfg.host,
                )
                logger.info("Langfuse tracing enabled (host=%s)", cfg.host)
            except Exception:
                logger.exception("Failed to initialise Langfuse client")
                self._client = None

    def shutdown(self) -> None:
        with self._lock:
            self._shutdown_locked()

    def _shutdown_locked(self) -> None:
        if self._client is not None:
            try:
                self._client.flush()
            except Exception:
                logger.exception("Error flushing Langfuse client")
            try:
                shutdown = getattr(self._client, "shutdown", None)
                if shutdown is not None:
                    shutdown()
            except Exception:
                logger.exception("Error shutting down Langfuse client")
        self._client = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    @property
    def host(self) -> Optional[str]:
        return self._cfg.host if self._cfg else None

    def client(self) -> Optional[Any]:
        return self._client


tracer = _Tracer()


@contextmanager
def trace_chat_turn(
    *,
    user_text: str,
    vendor: str,
    model: str,
    mcp_servers: list[str],
) -> Iterator["_ChatTurn"]:
    """Open a Langfuse trace covering a single chat turn.

    Yields a `_ChatTurn` helper. If tracing is disabled, the helper's
    methods become no-ops so the caller can stay oblivious.
    """
    client = tracer.client()
    if client is None:
        yield _ChatTurn(None, None, None)
        return

    trace = None
    generation = None
    try:
        trace = client.trace(
            name="chat_turn",
            input=user_text,
            metadata={
                "vendor": vendor,
                "model": model,
                "mcp_servers_enabled": mcp_servers,
            },
            tags=[f"vendor:{vendor}", f"model:{model}"],
        )
        generation = trace.generation(
            name="llm_call",
            model=model,
            model_parameters={"vendor": vendor},
            input=user_text,
        )
        yield _ChatTurn(client, trace, generation)
    except Exception:
        logger.exception("Langfuse trace setup failed; continuing without tracing")
        yield _ChatTurn(None, None, None)
    finally:
        try:
            if client is not None:
                client.flush()
        except Exception:
            logger.exception("Langfuse flush failed")


class _ChatTurn:
    def __init__(self, client: Any, trace: Any, generation: Any) -> None:
        self._client = client
        self._trace = trace
        self._generation = generation

    def finish_llm(
        self,
        *,
        output: str,
        usage: Optional[dict[str, int]] = None,
    ) -> None:
        if self._generation is None:
            return
        try:
            kwargs: dict[str, Any] = {"output": output}
            if usage:
                kwargs["usage"] = usage
            self._generation.end(**kwargs)
        except Exception:
            logger.exception("Langfuse generation.end failed")

    def finish_trace(self, *, output: str) -> None:
        if self._trace is None:
            return
        try:
            self._trace.update(output=output)
        except Exception:
            logger.exception("Langfuse trace.update failed")

    def record_error(self, err: str) -> None:
        if self._trace is None:
            return
        try:
            self._trace.update(
                output=err,
                level="ERROR",
                status_message=err,
            )
        except Exception:
            logger.exception("Langfuse trace error update failed")

    def span_tool_call(
        self,
        *,
        server_name: str,
        tool_name: str,
        arguments: dict[str, Any],
        result: Optional[str],
        error: Optional[str],
    ) -> None:
        """Record a completed MCP tool call as a child span."""
        if self._trace is None:
            return
        try:
            span = self._trace.span(
                name=f"tool:{server_name}.{tool_name}",
                input=arguments,
                metadata={"server_name": server_name, "tool_name": tool_name},
            )
            if error:
                span.end(output=error, level="ERROR", status_message=error)
            else:
                span.end(output=result)
        except Exception:
            logger.exception("Langfuse tool span failed")
