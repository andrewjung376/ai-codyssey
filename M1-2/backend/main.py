"""내 데이터를 아는 AI 비서 — FastAPI 진입점.

로컬 실행: uvicorn main:app --reload   (backend 폴더에서)
API 문서:  http://localhost:8000/docs
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from routers import chat, conversations, data
from services.repository import StorageUnavailable

app = FastAPI(
    title="My Data AI Assistant API",
    description="시계열 데이터(삼성전자 일별 종가) 요약을 GPT 시스템 프롬프트에 주입해 답하는 AI 비서 API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

@app.exception_handler(StorageUnavailable)
def storage_unavailable(_: Request, exc: StorageUnavailable):
    return JSONResponse(status_code=503, content={"detail": f"저장소를 사용할 수 없습니다: {exc}"})


app.include_router(data.router)
app.include_router(conversations.router)
app.include_router(chat.router)


@app.get("/health", tags=["health"], summary="헬스 체크 (콜드스타트 깨우기용)")
def health():
    return {"status": "ok", "storage": settings.storage_backend}
