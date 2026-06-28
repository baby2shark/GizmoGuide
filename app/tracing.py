"""Langfuse v4 tracing integration for GizmoGuide.

Uses the Langfuse Python SDK v4 which is built on OpenTelemetry.
Nested observations automatically inherit parent context via OTel.
When Langfuse is not configured all operations become silent no-ops.

Usage:
    from app.tracing import trace_request, trace_span, trace_generation

    with trace_request(session_id, user_id) as obs:
        with trace_span("step_name", input_data=...) as (span, end_span):
            ...
            end_span(output=...)

        with trace_generation("model_call", model="deepseek-chat", input_data=[...]) as (gen, end_gen):
            ...
            end_gen(output="...", usage_details={...})
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy client initialisation
# ---------------------------------------------------------------------------

_client: Any = None
_client_initialised = False


def _init_client() -> Any:
    """Initialise the Langfuse v4 client once, reading env vars automatically."""
    global _client, _client_initialised

    if _client_initialised:
        return _client

    _client_initialised = True

    try:
        from langfuse import Langfuse
    except ImportError:
        logger.debug("langfuse package not installed; tracing disabled")
        return None

    try:
        _client = Langfuse()
        logger.info("Langfuse v4 tracing initialised successfully")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to initialise Langfuse: %s", exc)
        _client = None

    return _client


def _get_client() -> Any:
    """Return the shared Langfuse client or *None* if unavailable."""
    return _init_client()


# ---------------------------------------------------------------------------
# Top-level trace lifecycle
# ---------------------------------------------------------------------------


@contextmanager
def trace_request(
    session_id: str,
    user_id: Optional[str] = None,
    input_data: Optional[Any] = None,
    metadata: Optional[dict] = None,
):
    """Create a root observation for a single API request.

    Yields the observation object (or *None* when tracing is off).
    Session and user info are stored in observation metadata.
    """
    client = _get_client()
    if client is None:
        yield None
        return

    meta = {"session_id": session_id, "user_id": user_id or session_id}
    if metadata:
        meta.update(metadata)

    with client.start_as_current_observation(
        name="gizmoguide_request",
        as_type="span",
        input=input_data,
        metadata=meta,
    ) as obs:
        yield obs

    try:
        client.flush()
    except Exception:  # noqa: BLE001
        logger.debug("Langfuse flush failed", exc_info=True)


# ---------------------------------------------------------------------------
# Span helpers (arbitrary processing steps)
# ---------------------------------------------------------------------------


@contextmanager
def trace_span(
    name: str,
    input_data: Any = None,
    metadata: Optional[dict] = None,
):
    """Open a child span under the active observation.

    Yields ``(span, end_span)`` where ``end_span(output=...)`` records output.
    No-op when tracing client is unavailable.
    OTel context propagation handles parent nesting automatically.
    """
    client = _get_client()
    if client is None:
        yield None, lambda **kw: None
        return

    with client.start_as_current_observation(
        name=name,
        as_type="span",
        input=input_data,
        metadata=metadata,
    ) as span:
        ended = False

        def end_span(
            output: Any = None,
            metadata_extra: Optional[dict] = None,
            level: str = "DEFAULT",
        ):
            nonlocal ended
            if ended:
                return
            ended = True
            kwargs: dict[str, Any] = {"level": level}
            if output is not None:
                kwargs["output"] = output
            if metadata_extra:
                kwargs["metadata"] = metadata_extra
            try:
                span.update(**kwargs)
            except Exception:  # noqa: BLE001
                logger.debug("Langfuse span update failed for %s", name, exc_info=True)

        try:
            yield span, end_span
        except Exception as exc:
            if not ended:
                try:
                    span.update(level="ERROR", status_message=str(exc))
                except Exception:  # noqa: BLE001
                    pass
                ended = True
            raise


# ---------------------------------------------------------------------------
# Generation helpers (LLM calls)
# ---------------------------------------------------------------------------


@contextmanager
def trace_generation(
    name: str,
    model: Optional[str] = None,
    input_data: Any = None,
    metadata: Optional[dict] = None,
):
    """Open a generation observation for an LLM call.

    Yields ``(generation, end_generation)`` where
    ``end_generation(output=..., usage_details={...})`` records the result.
    """
    client = _get_client()
    if client is None:
        yield None, lambda **kw: None
        return

    kwargs: dict[str, Any] = {
        "name": name,
        "as_type": "generation",
        "input": input_data,
        "metadata": metadata,
    }
    if model:
        kwargs["model"] = model

    with client.start_as_current_observation(**kwargs) as gen:
        ended = False

        def end_generation(
            output: Any = None,
            usage: Optional[dict] = None,
            usage_details: Optional[dict] = None,
            metadata_extra: Optional[dict] = None,
            level: str = "DEFAULT",
        ):
            nonlocal ended
            if ended:
                return
            ended = True
            upd: dict[str, Any] = {"level": level}
            if output is not None:
                upd["output"] = output
            # Support both v2-style "usage" and v4-style "usage_details"
            ud = usage_details or usage
            if ud:
                upd["usage_details"] = ud
            if metadata_extra:
                upd["metadata"] = metadata_extra
            try:
                gen.update(**upd)
            except Exception:  # noqa: BLE001
                logger.debug("Langfuse generation update failed for %s", name, exc_info=True)

        try:
            yield gen, end_generation
        except Exception as exc:
            if not ended:
                try:
                    gen.update(level="ERROR", status_message=str(exc))
                except Exception:  # noqa: BLE001
                    pass
                ended = True
            raise
