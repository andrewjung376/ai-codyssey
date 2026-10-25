"""GPT 호출과 컨텍스트 주입(데이터 요약 → 시스템 프롬프트).

호출 순서 (A1-3과 같은 방식)
  1순위 Codyssey 프록시  CODY_OPENAI_API_KEY → {CODY_BASE_URL}/chat/completions (httpx 직접 호출)
  2순위 OpenAI 공식 API  OPENAI_API_KEY      → openai SDK
1순위가 401·타임아웃·빈 응답 등으로 실패하면 2순위로 다시 시도한다.
"""

import logging
import threading
from functools import lru_cache
from typing import Protocol

import httpx

from core.config import settings

log = logging.getLogger(__name__)

KEY_SOURCE_CODY = "cody"
KEY_SOURCE_OPENAI = "openai"

SYSTEM_TEMPLATE = """당신은 사용자의 시계열 데이터를 이해하고 있는 데이터 분석 비서입니다.

[사용자 데이터 요약] — {dataset}
- 데이터 기간: {period}
- 총 레코드: {count}개
- 주요 지표({unit}): {metrics}
- 최근 트렌드: {trend}

[월별 통계] (월 | 평균 | 최고 | 최저 | 월말값)
{monthly}

[최근 데이터] (날짜 | 값 | 메모)
{recent}

답변 규칙
- 위 데이터에 근거해 구체적인 수치·날짜를 들어 한국어로 간결하게 답하세요.
- 데이터에 없는 내용은 추측하지 말고 "저장된 데이터로는 알 수 없다"고 말하세요.
- 투자 권유가 아닌 데이터 해석으로 답하고, 필요하면 그 점을 짧게 밝히세요."""


def _fmt(v: float) -> str:
    return f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.2f}"


def build_system_prompt(summary: dict) -> str:
    m = summary.get("metrics")
    if m:
        metrics = (
            f"평균 {_fmt(m['average'])}, 최고 {_fmt(m['max'])}({m['max_date']}), "
            f"최저 {_fmt(m['min'])}({m['min_date']}), 최신 {_fmt(m['latest'])}({m['latest_date']}), "
            f"기간 변화율 {m['change_pct']:+.2f}%, 일간 변동성 {m['volatility_pct']:.2f}%, "
            f"5일 이동평균 {_fmt(m['ma5'])}, 20일 이동평균 {_fmt(m['ma20'])}"
        )
    else:
        metrics = "데이터 없음"
    monthly = "\n".join(
        f"- {x['month']} | {_fmt(x['average'])} | {_fmt(x['max'])} | {_fmt(x['min'])} | {_fmt(x['last'])}"
        for x in summary.get("monthly", [])
    ) or "- 없음"
    recent = "\n".join(
        f"- {x['date']} | {_fmt(x['value'])} | {x.get('memo') or '-'}" for x in summary.get("recent", [])
    ) or "- 없음"
    return SYSTEM_TEMPLATE.format(
        dataset=summary["dataset"], unit=summary["unit"], period=summary["period"],
        count=summary["count"], metrics=metrics, trend=summary["trend"],
        monthly=monthly, recent=recent,
    )


class LLMClient(Protocol):
    def complete(self, messages: list[dict]) -> tuple[str, str]:
        """(답변, 사용한 키 소스 "cody" | "openai")"""
        ...


class LLMUnavailable(RuntimeError):
    pass


class CodyProxyClient:
    """Codyssey OpenAI 호환 프록시. openai SDK 없이 HTTP로 직접 호출한다.

    gpt-5-mini 는 추론 토큰도 출력 상한에 포함돼 상한을 작게 주면 빈 답이 나올 수 있어
    A1-3과 같이 토큰 상한을 보내지 않는다.
    """

    def __init__(self, api_key: str, base_url: str, model: str, timeout: float):
        self._url = f"{base_url}/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._model = model
        self._timeout = timeout

    def complete(self, messages: list[dict]) -> str:
        res = httpx.post(self._url, headers=self._headers, timeout=self._timeout,
                         json={"model": self._model, "messages": messages})
        res.raise_for_status()
        text = (res.json()["choices"][0]["message"]["content"] or "").strip()
        if not text:
            raise ValueError("Cody 프록시가 빈 응답을 돌려줬습니다.")
        return text


class OpenAIClient:
    def __init__(self, api_key: str, model: str, max_tokens: int, timeout: float):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, timeout=timeout, max_retries=1)
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, messages: list[dict]) -> str:
        res = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_completion_tokens=self._max_tokens,
        )
        return (res.choices[0].message.content or "").strip()


class FallbackLLM:
    """등록 순서대로 시도하고, 처음 성공한 공급자의 답과 키 소스를 돌려준다."""

    def __init__(self, providers: list[tuple[str, object]]):
        self._providers = providers

    def complete(self, messages: list[dict]) -> tuple[str, str]:
        last_error: Exception | None = None
        for source, client in self._providers:
            try:
                return client.complete(messages), source
            except Exception as e:  # 401·429·타임아웃·형식 오류 모두 다음 공급자로
                last_error = e
                # 키 값은 남기지 않고 상태 코드·오류 종류만 기록한다
                status = getattr(getattr(e, "response", None), "status_code", None)
                log.warning("LLM 호출 실패 [%s] status=%s %s", source, status, type(e).__name__)
        raise last_error


_llm_lock = threading.Lock()


def get_llm() -> LLMClient:
    """FastAPI 의존성. 키가 하나도 없으면 채팅 요청 시점에 503을 돌려준다."""
    with _llm_lock:  # 동시 첫 요청에서도 클라이언트를 한 번만 만든다
        return _build_llm()


@lru_cache
def _build_llm() -> LLMClient:
    providers: list[tuple[str, object]] = []
    if settings.cody_api_key:
        providers.append((KEY_SOURCE_CODY, CodyProxyClient(
            settings.cody_api_key, settings.cody_base_url, settings.cody_model, settings.cody_timeout)))
    if settings.openai_api_key:
        providers.append((KEY_SOURCE_OPENAI, OpenAIClient(
            settings.openai_api_key, settings.openai_model, settings.openai_max_tokens, settings.openai_timeout)))
    if not providers:
        raise LLMUnavailable("CODY_OPENAI_API_KEY 또는 OPENAI_API_KEY 가 설정되지 않았습니다.")
    return FallbackLLM(providers)
