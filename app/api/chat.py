from __future__ import annotations

import contextvars
import json
from collections.abc import Generator
from queue import Queue
from threading import Thread
from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.agent.purchase_agent import PurchaseDecisionAgent
from app.schemas.chat import ChatRequest, ChatResponse, ChatStreamEvent
from app.tracing import trace_request

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    with trace_request(
        session_id=request.session_id,
        user_id=request.user_id,
        input_data=request.model_dump(mode="json"),
    ) as trace:
        agent = PurchaseDecisionAgent()
        ctx = contextvars.copy_context()
        response = ctx.run(agent.chat, request)
        if trace:
            trace.update(output={"mode": response.mode, "answer_source": response.answer_source})
        return response


@router.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    request_id = uuid4().hex
    return StreamingResponse(
        _stream_chat_events(request, request_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _stream_chat_events(request: ChatRequest, request_id: str) -> Generator[str, None, None]:
    queue: Queue[ChatStreamEvent | object] = Queue()
    done = object()

    def emit(event: str, message: str, data: dict | None = None) -> None:
        payload = {"request_id": request_id, **(data or {})}
        queue.put(ChatStreamEvent(event=event, message=message, data=payload))

    yield _sse(
        ChatStreamEvent(
            event="status",
            message="已建立流式连接",
            data={"request_id": request_id, "session_id": request.session_id},
        )
    )

    def worker() -> None:
        with trace_request(
            session_id=request.session_id,
            user_id=request.user_id,
            input_data=request.model_dump(mode="json"),
        ) as trace:
            try:
                agent = PurchaseDecisionAgent()
                ctx = contextvars.copy_context()
                response = ctx.run(agent.chat_with_events, request, emit)
                queue.put(
                    ChatStreamEvent(
                        event="final",
                        message="回答生成完成",
                        data={
                            "request_id": request_id,
                            "response": response.model_dump(mode="json"),
                        },
                    )
                )
                _safe_trace_update(trace, output={"mode": response.mode, "answer_source": response.answer_source, "stream_request_id": request_id})
            except Exception as exc:  # noqa: BLE001
                queue.put(
                    ChatStreamEvent(
                        event="error",
                        message="流式回答生成失败",
                        data={
                            "request_id": request_id,
                            "error_type": type(exc).__name__,
                            "detail": str(exc),
                        },
                    )
                )
                _safe_trace_update(trace, output={"error": str(exc), "stream_request_id": request_id}, level="ERROR")
            finally:
                queue.put(done)

    Thread(target=worker, daemon=True).start()

    while True:
        item = queue.get()
        if item is done:
            break
        yield _sse(item)


def _sse(event: ChatStreamEvent) -> str:
    payload = event.model_dump(mode="json")
    data = json.dumps(payload, ensure_ascii=False)
    return f"event: {event.event}\ndata: {data}\n\n"


def _safe_trace_update(trace: Any, **kwargs: Any) -> None:
    if not trace:
        return
    try:
        trace.update(**kwargs)
    except TypeError:
        kwargs.pop("level", None)
        trace.update(**kwargs)
