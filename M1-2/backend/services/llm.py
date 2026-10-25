"""GPT 호출과 컨텍스트 주입(데이터 요약 → 시스템 프롬프트)."""

from functools import lru_cache
from typing import Protocol

from core.config import settings

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
    def complete(self, messages: list[dict]) -> str: ...


class LLMUnavailable(RuntimeError):
    pass


class OpenAIClient:
    def __init__(self, api_key: str, model: str, max_tokens: int):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, timeout=30, max_retries=1)
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, messages: list[dict]) -> str:
        res = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_completion_tokens=self._max_tokens,
        )
        return (res.choices[0].message.content or "").strip()


@lru_cache
def get_llm() -> LLMClient:
    """FastAPI 의존성. 키가 없으면 채팅 요청 시점에 503을 돌려준다."""
    if not settings.openai_api_key:
        raise LLMUnavailable("OPENAI_API_KEY 가 설정되지 않았습니다.")
    return OpenAIClient(settings.openai_api_key, settings.openai_model, settings.openai_max_tokens)
