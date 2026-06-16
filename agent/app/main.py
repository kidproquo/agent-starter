from __future__ import annotations

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .admin_config import router as admin_router
from .agent import run_agent
from .auth.bootstrap import ensure_bootstrap_admin
from .auth.deps import UserContext, get_current_user
from .auth.routes import router as auth_router
from .config import settings
from .db import close_db, init_db
from .extract import extract_text
from .models_meta import router as models_router
from .schemas import PromptContext, PromptRequest

_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB

app = FastAPI(title="agent-starter", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    # Cookie-based sessions: the browser must send the session cookie on API
    # calls, which requires credentialed CORS (and a non-wildcard origin list).
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(models_router)


@app.on_event("startup")
async def _startup() -> None:
    await init_db()
    await ensure_bootstrap_admin()


@app.on_event("shutdown")
async def _shutdown() -> None:
    await close_db()


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True, "model": settings.model}


@app.post("/chat")
async def chat(
    req: PromptRequest,
    user: UserContext = Depends(get_current_user),
) -> StreamingResponse:
    return StreamingResponse(
        run_agent(req, user=user),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@app.post("/chat/upload")
async def chat_upload(
    prompt: str = Form(...),
    file: UploadFile = File(...),
    conversation_id: str | None = Form(None),
    user: UserContext = Depends(get_current_user),
) -> StreamingResponse:
    """Multipart variant of /chat for an attached document. The file is
    extracted to text server-side and passed straight to the agent as
    attachment_text — the extracted text never round-trips back to the browser."""
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"file too large (max {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
        )
    try:
        attachment_text, _ = extract_text(file.filename, file.content_type, data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"{file.filename!r}: {e}")

    req = PromptRequest(
        prompt=prompt,
        context=PromptContext(conversation_id=conversation_id, attachment_text=attachment_text),
    )
    return StreamingResponse(
        run_agent(req, user=user),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
