from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.chat import router as chat_router
from app.api.products import router as products_router
from app.api.recommend import router as recommend_router

ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"

app = FastAPI(title="GizmoGuide", version="0.1.0")
app.include_router(chat_router)
app.include_router(products_router)
app.include_router(recommend_router)

if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=FRONTEND_DIR, html=True), name="ui")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "GizmoGuide"}


@app.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    return RedirectResponse(url="/ui/")