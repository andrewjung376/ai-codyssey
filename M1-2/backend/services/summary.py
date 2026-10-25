"""시계열 요약 계산. 결과는 /api/data/summary 응답과 GPT 시스템 프롬프트에 함께 쓰인다."""

import statistics
from collections import OrderedDict

from core.config import settings

TREND_WINDOW = 20      # 최근 추세 판단 구간(데이터 포인트 수)
TREND_THRESHOLD = 2.0  # 이 비율(%) 이상 움직여야 상승/하락으로 본다
RECENT_COUNT = 10


def _r(x: float) -> float:
    return round(x, 2)


def _trend(values: list[float]) -> str:
    if len(values) < 2:
        return "판단 불가 (데이터 부족)"
    window = min(TREND_WINDOW, len(values) - 1)
    base, last = values[-1 - window], values[-1]
    pct = (last - base) / base * 100 if base else 0.0
    label = "상승" if pct >= TREND_THRESHOLD else "하락" if pct <= -TREND_THRESHOLD else "유지"
    return f"{label} (최근 {window}개 구간 {pct:+.1f}%)"


def _monthly(items: list[dict]) -> list[dict]:
    groups: "OrderedDict[str, list[float]]" = OrderedDict()
    for it in items:
        groups.setdefault(it["date"][:7], []).append(it["value"])
    return [
        {"month": m, "average": _r(statistics.fmean(v)), "max": max(v), "min": min(v),
         "last": v[-1], "count": len(v)}
        for m, v in groups.items()
    ]


def build_summary(items: list[dict]) -> dict:
    """items 는 날짜 오름차순 정렬된 {id, date(YYYY-MM-DD), value, memo} 목록."""
    base = {"dataset": settings.dataset_name, "unit": settings.dataset_unit}
    if not items:
        return {**base, "period": "-", "count": 0, "metrics": None,
                "trend": "판단 불가 (데이터 없음)", "monthly": [], "recent": []}

    values = [it["value"] for it in items]
    max_it = max(items, key=lambda it: it["value"])
    min_it = min(items, key=lambda it: it["value"])
    returns = [(b - a) / a * 100 for a, b in zip(values, values[1:]) if a]

    metrics = {
        "total": _r(sum(values)),
        "average": _r(statistics.fmean(values)),
        "max": max_it["value"], "max_date": max_it["date"],
        "min": min_it["value"], "min_date": min_it["date"],
        "latest": values[-1], "latest_date": items[-1]["date"],
        "change_pct": _r((values[-1] - values[0]) / values[0] * 100) if values[0] else 0.0,
        "volatility_pct": _r(statistics.pstdev(returns)) if len(returns) > 1 else 0.0,
        "ma5": _r(statistics.fmean(values[-5:])),
        "ma20": _r(statistics.fmean(values[-20:])),
    }
    return {
        **base,
        "period": f"{items[0]['date']} ~ {items[-1]['date']}",
        "count": len(items),
        "metrics": metrics,
        "trend": _trend(values),
        "monthly": _monthly(items),
        "recent": items[-RECENT_COUNT:],
    }
