"""대시보드용 Plotly 차트 (PRD 6.1). 리포트용 matplotlib 그래프는 viz.py에 있다.

모든 함수는 plotly Figure를 돌려준다. 집계는 features.py를 써서 노트북과 같은 수치를 낸다.
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import features as F
from .viz import SERVICE_COLORS, SERVICE_NAMES, service_label

_LAYOUT = dict(margin=dict(l=10, r=10, t=50, b=10), legend=dict(orientation="h", y=-0.15), template="plotly_white")


def _ordered(services) -> list[str]:
    services = list(services)
    return [s for s in SERVICE_NAMES if s in services] + [s for s in services if s not in SERVICE_NAMES]


def add_phases(fig: go.Figure, phases) -> go.Figure:
    """생활 단계 시작일에 세로 점선과 이름을 그린다. phases: [(이름, 시작일)]. 첫 단계는 선을 긋지 않는다."""
    for name, start in (phases or [])[1:]:
        x = pd.Timestamp(start)
        # 밝은·어두운 테마 모두에서 보이도록 중간 회색을 쓴다
        fig.add_shape(type="line", x0=x, x1=x, y0=0, y1=1, xref="x", yref="paper",
                      line=dict(color="#8C8C8C", dash="dot", width=1.2))
        fig.add_annotation(x=x, y=1, xref="x", yref="paper", text=name, showarrow=False,
                           xanchor="left", yanchor="bottom", font=dict(size=12, color="#8C8C8C"))
    return fig


def trend_chart(series: dict[str, pd.Series], window: int, sources=None, outliers=None, phases=None) -> go.Figure:
    """서비스별 건수와 이동평균, 이상치 마커 (FR-04, FR-09)."""
    services = _ordered(series)
    fig = make_subplots(rows=len(services), cols=1, shared_xaxes=True, vertical_spacing=0.07,
                        subplot_titles=[service_label(s, sources) for s in services])
    for row, svc in enumerate(services, start=1):
        s, color = series[svc], SERVICE_COLORS.get(svc, "gray")
        fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", name="건수", opacity=0.35,
                                 line=dict(color=color, width=1), showlegend=row == 1, legendgroup="raw"), row, 1)
        fig.add_trace(go.Scatter(x=s.index, y=F.moving_average(s, window), mode="lines",
                                 name=f"이동평균 ({window}구간)", line=dict(color=color, width=2.5),
                                 showlegend=row == 1, legendgroup="ma"), row, 1)
        if outliers is not None and svc in outliers:
            o = s[outliers[svc].reindex(s.index, fill_value=False)]
            fig.add_trace(go.Scatter(x=o.index, y=o.values, mode="markers", name="이상치",
                                     marker=dict(color="black", size=8, symbol="circle-open", line=dict(width=2)),
                                     showlegend=row == 1, legendgroup="out"), row, 1)
        fig.update_yaxes(title_text="건수", row=row, col=1)
    fig.update_layout(height=240 * len(services) + 80, hovermode="x unified", **_LAYOUT)
    return add_phases(fig, phases)


def change_chart(series: dict[str, pd.Series], sources=None) -> go.Figure:
    """직전 구간 대비 변화율(%) 막대 (FR-05)."""
    services = _ordered(series)
    fig = make_subplots(rows=len(services), cols=1, shared_xaxes=True, vertical_spacing=0.07,
                        subplot_titles=[service_label(s, sources) for s in services])
    for row, svc in enumerate(services, start=1):
        pct = F.pct_change(series[svc]).dropna()
        fig.add_trace(go.Bar(x=pct.index, y=pct.values, showlegend=False,
                             marker_color=["#4C78A8" if v >= 0 else "#E45756" for v in pct.values],
                             hovertemplate="%{x|%Y-%m-%d}: %{y:.1f}%<extra></extra>"), row, 1)
        fig.update_yaxes(title_text="%", row=row, col=1)
    fig.update_layout(height=200 * len(services) + 60, **_LAYOUT)
    return fig


def heatmap_chart(matrix: pd.DataFrame, title: str) -> go.Figure:
    """요일×시간 히트맵, 전체 대비 비율(%) (FR-06)."""
    share = matrix / max(matrix.to_numpy().sum(), 1) * 100
    fig = px.imshow(share, aspect="auto", color_continuous_scale="YlOrRd",
                    labels=dict(x="시간", y="요일", color="비율(%)"), title=title)
    fig.update_xaxes(tickvals=list(range(0, 24, 3)), ticktext=[f"{h}시" for h in range(0, 24, 3)])
    fig.update_layout(height=360, **_LAYOUT)
    return fig


def distribution_chart(events: pd.DataFrame, sources=None) -> go.Figure:
    """서비스별 요일·시간대 분포 비율 (FR-06)."""
    fig = make_subplots(rows=1, cols=2, subplot_titles=["요일별 비율(%)", "시간대별 비율(%)"], column_widths=[0.4, 0.6])
    for svc in _ordered(events["service"].astype(str).unique()):
        ts = events.loc[events["service"] == svc, "ts_kst"]
        color, name = SERVICE_COLORS.get(svc, "gray"), service_label(svc, sources)
        days = ts.dt.weekday.value_counts(normalize=True).reindex(range(7), fill_value=0) * 100
        hours = ts.dt.hour.value_counts(normalize=True).reindex(range(24), fill_value=0) * 100
        fig.add_trace(go.Bar(x=F.WEEKDAYS, y=days.values, name=name, marker_color=color, legendgroup=svc), 1, 1)
        fig.add_trace(go.Scatter(x=hours.index, y=hours.values, mode="lines+markers", name=name,
                                 line=dict(color=color), legendgroup=svc, showlegend=False), 1, 2)
    fig.update_xaxes(tickvals=list(range(0, 24, 3)), ticktext=[f"{h}시" for h in range(0, 24, 3)], row=1, col=2)
    fig.update_layout(height=380, barmode="group", **_LAYOUT)
    return fig


def top_n_chart(counts: pd.Series, title: str, color: str = "#4C78A8") -> go.Figure:
    """상위 항목 가로 막대 (FR-07, FR-19)."""
    counts = counts[::-1]
    fig = go.Figure(go.Bar(x=counts.values, y=[str(i) for i in counts.index], orientation="h", marker_color=color))
    fig.update_layout(title=title, height=max(260, 28 * len(counts) + 90), **_LAYOUT)
    return fig


def track_chart(events: pd.DataFrame, keywords: list[str], unit: str = "W", column: str = "label") -> go.Figure:
    """입력한 키워드가 포함된 항목의 시간별 등장 수 (FR-10)."""
    fig = go.Figure()
    values = events[column].astype("string")
    for kw in keywords:
        hit = events[values.str.contains(kw, case=False, regex=False, na=False)]
        if hit.empty:
            continue
        s = F.resample(F.daily_counts(hit, by=None, start=events["ts_kst"].min().date(),
                                      end=events["ts_kst"].max().date())["total"], unit)
        fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines+markers", name=f"{kw} ({len(hit):,}건)"))
    fig.update_layout(title="키워드 추적", height=380, hovermode="x unified", **_LAYOUT)
    return fig


def profile_compare_chart(watch: pd.DataFrame) -> go.Figure:
    """프로필(내 채널)별 시청 시간대·요일 분포 (FR-16)."""
    fig = make_subplots(rows=1, cols=2, subplot_titles=["시간대별 시청 비율(%)", "요일별 시청 비율(%)"])
    for i, (profile, g) in enumerate(watch.groupby("profile", observed=True)):
        color = px.colors.qualitative.Set2[i % 8]
        hours = g["ts_kst"].dt.hour.value_counts(normalize=True).reindex(range(24), fill_value=0) * 100
        days = g["ts_kst"].dt.weekday.value_counts(normalize=True).reindex(range(7), fill_value=0) * 100
        fig.add_trace(go.Scatter(x=hours.index, y=hours.values, mode="lines+markers", name=str(profile),
                                 line=dict(color=color), legendgroup=str(profile)), 1, 1)
        fig.add_trace(go.Bar(x=F.WEEKDAYS, y=days.values, name=str(profile), marker_color=color,
                             legendgroup=str(profile), showlegend=False), 1, 2)
    fig.update_layout(height=380, barmode="group", **_LAYOUT)
    return fig


def domain_trend_chart(web: pd.DataFrame, k: int = 6, column: str = "label", phases=None) -> go.Figure:
    """상위 k개 도메인의 월별 방문 추세 (FR-19)."""
    top = web[column].value_counts().head(k).index
    month = web["ts_kst"].dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()
    table = pd.crosstab(month, web[column])[list(top)]
    fig = go.Figure([go.Scatter(x=table.index, y=table[c], mode="lines+markers", name=str(c)) for c in table.columns])
    fig.update_layout(title=f"상위 {k}개 도메인 월별 방문", height=400, hovermode="x unified", **_LAYOUT)
    return add_phases(fig, phases)


def combined_area_chart(series: dict[str, pd.Series], sources=None, phases=None) -> go.Figure:
    """서비스별 주간 활동량 누적 영역, 모든 서비스의 공통 기간 (FR-21)."""
    services = _ordered(series)
    start = max(series[s].index.min() for s in services)
    end = min(series[s].index.max() for s in services)
    fig = go.Figure()
    for svc in services:
        weekly = F.resample(series[svc].loc[start:end], "W")
        fig.add_trace(go.Scatter(x=weekly.index, y=weekly.values, stackgroup="one", name=service_label(svc, sources),
                                 line=dict(color=SERVICE_COLORS.get(svc, "gray"))))
    fig.update_layout(title=f"서비스별 주간 활동량 ({start:%Y-%m-%d} ~ {end:%Y-%m-%d})", height=400,
                      hovermode="x unified", **_LAYOUT)
    visible = [(n, d) for n, d in (phases or []) if start < pd.Timestamp(d) <= end]
    return add_phases(fig, [("", start), *visible])


def phase_chart(series: dict[str, pd.Series], phases, sources=None) -> go.Figure:
    """생활 단계별 일평균 건수 (Q8)."""
    names = [n for n, _ in phases]
    fig = go.Figure()
    for svc in _ordered(series):
        s = series[svc]
        phase = F.assign_phase(s.index, phases).to_numpy()
        means = [s[phase == n].mean() if (phase == n).any() else None for n in names]
        fig.add_trace(go.Bar(x=names, y=means, name=service_label(svc, sources),
                             marker_color=SERVICE_COLORS.get(svc, "gray"), texttemplate="%{y:.1f}", textposition="outside"))
    fig.update_layout(title="단계별 일평균 건수", barmode="group", height=400, **_LAYOUT)
    return fig
