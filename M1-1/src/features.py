"""시계열 집계와 분석 지표 (PRD FR-04~06, 4.4 결측·이상치 규칙).

일별 집계에서 활동이 없는 날은 결측이 아니라 실제 0으로 채운다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
# 주는 월요일 시작, 월은 1일 시작으로 라벨을 붙인다
_RESAMPLE = {"W": dict(rule="W-MON", label="left", closed="left"), "M": dict(rule="MS")}


def _local_dates(events: pd.DataFrame) -> pd.Series:
    return events["ts_kst"].dt.tz_localize(None).dt.normalize()


def daily_counts(events: pd.DataFrame, by: str | None = "service",
                 start: str | pd.Timestamp | None = None, end: str | pd.Timestamp | None = None) -> pd.DataFrame:
    """일별 건수. by 컬럼 값마다 열 하나 (by=None이면 'total' 열 하나). 빈 날은 0."""
    dates = _local_dates(events)
    if by is None:
        counts = dates.value_counts().to_frame("total")
    else:
        counts = pd.crosstab(dates, events[by])
        counts.columns = counts.columns.astype(str)
    if counts.empty:
        return counts
    index = pd.date_range(start or counts.index.min(), end or counts.index.max(), freq="D", name="date")
    return counts.reindex(index, fill_value=0).astype(int)


def resample(daily: pd.DataFrame | pd.Series, unit: str = "D") -> pd.DataFrame | pd.Series:
    """일별 집계를 일(D)·주(W)·월(M) 단위 합계로 바꾼다."""
    if unit == "D":
        return daily
    return daily.resample(**_RESAMPLE[unit]).sum()


def moving_average(data: pd.DataFrame | pd.Series, window: int = 7) -> pd.DataFrame | pd.Series:
    return data.rolling(window, min_periods=window).mean()


def pct_change(data: pd.DataFrame | pd.Series) -> pd.DataFrame | pd.Series:
    """직전 구간 대비 변화율(%). 직전 값이 0이면 NaN."""
    return (data.pct_change() * 100).replace([np.inf, -np.inf], np.nan)


def flag_outliers(series: pd.Series, k: float = 3.0) -> pd.Series:
    """Q3 + k×IQR을 넘는 날을 True로 표시한다. 값은 제거하지 않는다."""
    q1, q3 = series.quantile([0.25, 0.75])
    return series > q3 + k * (q3 - q1)


def find_gaps(series: pd.Series, max_zero_days: int = 7) -> pd.DataFrame:
    """0이 max_zero_days일보다 길게 이어진 구간 (기록 중단 의심)."""
    is_zero = series.eq(0)
    run_id = (is_zero != is_zero.shift()).cumsum()
    rows = []
    for _, run in series[is_zero].groupby(run_id[is_zero]):
        if len(run) > max_zero_days:
            rows.append({"start": run.index.min(), "end": run.index.max(), "days": len(run)})
    return pd.DataFrame(rows, columns=["start", "end", "days"])


def combined_daily(events: pd.DataFrame) -> pd.DataFrame:
    """서비스별 일별 건수와 합계(total) 열 (FR-21 통합 활동량)."""
    daily = daily_counts(events)
    daily["total"] = daily.sum(axis=1)
    return daily


def top_n(events: pd.DataFrame, column: str, n: int = 10, service: str | None = None) -> pd.Series:
    """column 값(검색어·콘텐츠 채널·도메인 등)의 상위 n개 건수 (FR-07, FR-19)."""
    if service is not None:
        events = events[events["service"] == service]
    return events[column].dropna().value_counts().head(n)


def weekday_hour_matrix(events: pd.DataFrame) -> pd.DataFrame:
    """요일(월~일) × 시간(0~23) 활동 건수."""
    ts = events["ts_kst"]
    matrix = pd.crosstab(ts.dt.weekday, ts.dt.hour)
    matrix = matrix.reindex(index=range(7), columns=range(24), fill_value=0)
    matrix.index = WEEKDAYS
    matrix.index.name, matrix.columns.name = "weekday", "hour"
    return matrix
