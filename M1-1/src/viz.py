"""리포트용 matplotlib 그래프 (images/*.png).

모든 함수는 Figure를 돌려준다. 저장은 save()로 한다.
샘플 데이터로 그린 서비스는 범례·제목에 "(샘플)"을 붙여 실제 데이터와 구분한다.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager

from .features import WEEKDAYS, moving_average

ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = ROOT / "images"
SERVICE_NAMES = {"search": "Google 검색", "yt_watch": "YouTube 시청", "yt_search": "YouTube 검색", "web_visit": "웹 방문"}
SERVICE_COLORS = {"search": "#4C78A8", "yt_watch": "#E45756", "yt_search": "#F58518", "web_visit": "#54A24B"}
_KOREAN_FONTS = ("Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR", "Noto Sans KR")


def setup_style() -> str | None:
    """한글 폰트와 기본 스타일을 설정하고, 사용한 폰트 이름을 돌려준다."""
    available = {f.name for f in font_manager.fontManager.ttflist}
    font = next((f for f in _KOREAN_FONTS if f in available), None)
    if font:
        matplotlib.rcParams["font.family"] = font
    matplotlib.rcParams.update({
        "axes.unicode_minus": False, "figure.dpi": 110, "savefig.dpi": 130,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.3,
    })
    return font


def service_label(service: str, sources: dict[str, str] | None = None) -> str:
    name = SERVICE_NAMES.get(service, service)
    return f"{name} (샘플)" if sources and sources.get(service) == "sample" else name


def save(fig: plt.Figure, name: str, directory: Path = IMAGES_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    fig.savefig(path, bbox_inches="tight")
    return path


def _ordered(series: dict[str, pd.Series]) -> list[str]:
    return [s for s in SERVICE_NAMES if s in series] + [s for s in series if s not in SERVICE_NAMES]


def plot_daily_trend(series: dict[str, pd.Series], sources=None, windows=(7, 28)) -> plt.Figure:
    """서비스별 일별 건수와 이동평균 (Q1)."""
    services = _ordered(series)
    fig, axes = plt.subplots(len(services), 1, figsize=(12, 2.6 * len(services)), sharex=True, squeeze=False)
    for ax, svc in zip(axes[:, 0], services):
        s, color = series[svc], SERVICE_COLORS.get(svc, "gray")
        ax.plot(s.index, s.values, color=color, alpha=0.25, lw=0.8, label="일별")
        for w, style in zip(windows, ("-", "--")):
            ax.plot(s.index, moving_average(s, w), color=color, lw=1.8 if w == windows[0] else 1.4,
                    ls=style, label=f"{w}일 이동평균")
        ax.set_title(service_label(svc, sources), loc="left", fontsize=11)
        ax.set_ylabel("건수")
        ax.legend(loc="upper left", fontsize=8, ncol=3)
    fig.suptitle("서비스별 일별 활동과 이동평균", fontsize=13, x=0.01, ha="left")
    fig.tight_layout()
    return fig


def plot_weekly_change(weekly_pct: dict[str, pd.Series], sources=None, clip=(-100, 300)) -> plt.Figure:
    """주간 변화율(WoW %) 막대. 범위를 넘는 값은 잘라서 표시하고 ▲로 표시한다."""
    services = _ordered(weekly_pct)
    fig, axes = plt.subplots(len(services), 1, figsize=(12, 2.3 * len(services)), sharex=True, squeeze=False)
    for ax, svc in zip(axes[:, 0], services):
        s = weekly_pct[svc].dropna()
        clipped = s.clip(*clip)
        colors = np.where(s >= 0, "#4C78A8", "#E45756")
        ax.bar(s.index, clipped, width=5, color=colors)
        over = s[s > clip[1]]
        ax.scatter(over.index, [clip[1]] * len(over), marker="^", color="black", s=14, zorder=3)
        ax.axhline(0, color="black", lw=0.8)
        ax.set_ylim(clip[0] - 10, clip[1] + 25)
        ax.set_title(service_label(svc, sources), loc="left", fontsize=11)
        ax.set_ylabel("전주 대비 %")
    fig.suptitle(f"주간 변화율 (▲: {clip[1]}% 초과)", fontsize=13, x=0.01, ha="left")
    fig.tight_layout()
    return fig


def plot_heatmaps(matrices: dict[str, pd.DataFrame], sources=None) -> plt.Figure:
    """서비스별 요일×시간 히트맵 (Q2). 서비스마다 전체 대비 비율(%)로 정규화한다."""
    services = _ordered(matrices)
    cols = 2 if len(services) > 1 else 1
    rows = int(np.ceil(len(services) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(7 * cols, 3.0 * rows), squeeze=False)
    for ax, svc in zip(axes.flat, services):
        m = matrices[svc]
        share = m / max(m.to_numpy().sum(), 1) * 100
        im = ax.imshow(share.to_numpy(), aspect="auto", cmap="YlOrRd")
        ax.set_yticks(range(7), WEEKDAYS)
        ax.set_xticks(range(0, 24, 3), [f"{h}시" for h in range(0, 24, 3)])
        ax.grid(False)
        ax.set_title(service_label(svc, sources), loc="left", fontsize=11)
        fig.colorbar(im, ax=ax, label="비율(%)", fraction=0.04)
    for ax in list(axes.flat)[len(services):]:
        ax.set_visible(False)
    fig.suptitle("요일 × 시간대 활동 분포", fontsize=13, x=0.01, ha="left")
    fig.tight_layout()
    return fig


def plot_outliers_gaps(series: dict[str, pd.Series], outliers: dict[str, pd.Series],
                       gaps: dict[str, pd.DataFrame], sources=None) -> plt.Figure:
    """일별 건수에 이상치(●)와 기록 중단 의심 구간(회색 음영)을 표시한다 (Q3, 데이터 품질)."""
    services = _ordered(series)
    fig, axes = plt.subplots(len(services), 1, figsize=(12, 2.4 * len(services)), sharex=True, squeeze=False)
    for ax, svc in zip(axes[:, 0], services):
        s = series[svc]
        ax.plot(s.index, s.values, color=SERVICE_COLORS.get(svc, "gray"), lw=0.9)
        flagged = s[outliers[svc]]
        ax.scatter(flagged.index, flagged.values, color="black", s=22, zorder=3,
                   label=f"이상치 {len(flagged)}일")
        for _, g in gaps[svc].iterrows():
            ax.axvspan(g["start"], g["end"] + pd.Timedelta(days=1), color="gray", alpha=0.25, lw=0)
        ax.set_title(f"{service_label(svc, sources)}  (기록 중단 의심 {len(gaps[svc])}구간)", loc="left", fontsize=11)
        ax.set_ylabel("건수")
        ax.legend(loc="upper left", fontsize=8)
    fig.suptitle("이상치와 기록 중단 의심 구간", fontsize=13, x=0.01, ha="left")
    fig.tight_layout()
    return fig


def plot_top_by_quarter(panels: list[tuple[str, pd.DataFrame, str]], n: int = 5) -> plt.Figure:
    """분기별 상위 항목 (Q4). panels: [(행 제목, events 부분집합, 집계할 컬럼)]."""
    quarters = sorted({q for _, ev, _ in panels for q in ev["ts_kst"].dt.tz_localize(None).dt.to_period("Q")})
    fig, axes = plt.subplots(len(panels), len(quarters), figsize=(3.4 * len(quarters), 2.6 * len(panels)),
                             squeeze=False)
    for r, (title, ev, column) in enumerate(panels):
        period = ev["ts_kst"].dt.tz_localize(None).dt.to_period("Q")
        for c, q in enumerate(quarters):
            ax = axes[r, c]
            top = ev.loc[period == q, column].dropna().value_counts().head(n)[::-1]
            ax.set_title(f"{q.year}년 {q.quarter}분기" if r == 0 else "", fontsize=10)
            if top.empty:
                ax.text(0.5, 0.5, "데이터 없음", ha="center", va="center", color="gray", transform=ax.transAxes)
                ax.set_xticks([])
                ax.set_yticks([])
                ax.grid(False)
            else:
                ax.barh([str(x)[:18] for x in top.index], top.values, color="#4C78A8")
                ax.tick_params(axis="y", labelsize=8)
            if c == 0:
                ax.set_ylabel(title, fontsize=10)
    fig.suptitle(f"분기별 상위 {n}개 항목", fontsize=13, x=0.01, ha="left")
    fig.tight_layout()
    return fig


def plot_profile_compare(watch_events: pd.DataFrame) -> plt.Figure:
    """프로필(내 채널)별 시청 시간대·요일 분포 비율 (Q6)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 3.8))
    for profile, g in watch_events.groupby("profile", observed=True):
        hours = g["ts_kst"].dt.hour.value_counts(normalize=True).reindex(range(24), fill_value=0) * 100
        ax1.plot(hours.index, hours.values, marker="o", ms=3, label=str(profile))
        days = g["ts_kst"].dt.weekday.value_counts(normalize=True).reindex(range(7), fill_value=0) * 100
        ax2.plot(WEEKDAYS, days.values, marker="o", ms=4, label=str(profile))
    ax1.set_xticks(range(0, 24, 3), [f"{h}시" for h in range(0, 24, 3)])
    ax1.set(title="시간대별 시청 비율", ylabel="비율(%)")
    ax2.set(title="요일별 시청 비율", ylabel="비율(%)")
    ax1.legend(fontsize=9)
    fig.suptitle("내 채널(프로필)별 YouTube 시청 패턴", fontsize=13, x=0.01, ha="left")
    fig.tight_layout()
    return fig


def plot_domain_trend(web_events: pd.DataFrame, label_column: str = "label", k: int = 6,
                      title_suffix: str = "") -> plt.Figure:
    """상위 k개 도메인(가린 이름)의 월별 방문 추세 (Q7)."""
    top = web_events[label_column].value_counts().head(k).index
    month = web_events["ts_kst"].dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()
    table = pd.crosstab(month, web_events[label_column])[list(top)]
    fig, ax = plt.subplots(figsize=(12, 4))
    for col in table.columns:
        ax.plot(table.index, table[col], marker="o", ms=4, label=str(col))
    ax.set(ylabel="월 방문 수")
    ax.legend(fontsize=9, ncol=3, loc="upper left")
    ax.set_title(f"상위 {k}개 도메인 월별 방문 추세{title_suffix}", loc="left", fontsize=13)
    fig.tight_layout()
    return fig


def plot_combined_activity(series: dict[str, pd.Series], sources=None) -> plt.Figure:
    """서비스별 주간 활동량 누적 영역 (Q7). 모든 서비스에 데이터가 있는 공통 기간만 그린다."""
    services = _ordered(series)
    start = max(series[s].index.min() for s in services)
    end = min(series[s].index.max() for s in services)
    frame = pd.DataFrame({s: series[s].loc[start:end] for s in services}).fillna(0)
    weekly = frame.resample("W-MON", label="left", closed="left").sum()
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.stackplot(weekly.index, weekly.T.to_numpy(), labels=[service_label(s, sources) for s in services],
                 colors=[SERVICE_COLORS.get(s, "gray") for s in services], alpha=0.85)
    ax.set(ylabel="주간 건수")
    ax.legend(loc="upper left", fontsize=9, ncol=len(services))
    ax.set_title(f"서비스별 주간 활동량 ({start:%Y-%m-%d} ~ {end:%Y-%m-%d})", loc="left", fontsize=13)
    fig.tight_layout()
    return fig
