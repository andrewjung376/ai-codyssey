"""환경 변수 기반 설정.

키·서비스 계정 정보는 코드에 두지 않고 .env(로컬) 또는 Render 환경 변수(배포)로만 주입한다.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


def _split_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    # 과금 방지용 응답 토큰 상한
    openai_max_tokens: int = int(os.getenv("OPENAI_MAX_TOKENS", "600"))
    # JSON 문자열 그 자체 또는 키 파일 경로
    firebase_service_account: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    # firestore(기본) | memory(키 없이 로컬 개발·테스트할 때)
    storage_backend: str = os.getenv("STORAGE_BACKEND", "firestore").lower()
    allowed_origins: list[str] = field(
        default_factory=lambda: _split_csv(
            os.getenv("ALLOWED_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500")
        )
    )
    dataset_name: str = os.getenv("DATASET_NAME", "삼성전자(005930.KS) 일별 종가")
    dataset_unit: str = os.getenv("DATASET_UNIT", "원")
    # 대화 이어가기 시 GPT에 함께 보내는 이전 메시지 수
    chat_history_limit: int = int(os.getenv("CHAT_HISTORY_LIMIT", "10"))


settings = Settings()
