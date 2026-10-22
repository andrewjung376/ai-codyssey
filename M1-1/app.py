"""My Activity Lens 대시보드 (PRD 6장).

실행: streamlit run app.py
- 샘플 데이터: 개인정보가 없는 합성 데이터 (기본값, 배포 데모용)
- 파일 업로드: Takeout zip·json·csv. 메모리에서만 처리하고 저장하지 않는다 (NFR-01)
- 로컬 data/raw: data/raw/에 데이터가 있을 때만 나타난다 (로컬 실행 전용)
"""
from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

import pandas as pd
import streamlit as st

from src import charts
from src import features as F
from src.dashboard import LABEL_KINDS, add_labels, parse_phases, profile_aliases
from src.datasource import RAW_DIR, SAMPLE_DIR, Dataset, build_dataset, group_uploads, load_dir
from src.profiles import channel_overlap
from src.viz import SERVICE_COLORS, SERVICE_NAMES, service_label

RAW = Path(os.environ.get("MYACTIVITY_RAW_DIR", RAW_DIR))
SAMPLE = Path(os.environ.get("MYACTIVITY_SAMPLE_DIR", SAMPLE_DIR))
SOURCES = {"sample": "샘플 데이터", "upload": "파일 업로드", "raw": "로컬 data/raw"}
UNITS = {"D": "일", "W": "주", "M": "월"}
# 로컬 data/raw 모드의 기본 생활 단계 (REPORT.md와 같은 경계일)
REPORT_PHASES = "재직, 2025-01-01\n퇴사 후, 2026-04-01\nAI 교육, 2026-04-27\nAI 과정, 2026-07-01"
_DATA_SUFFIXES = {".zip", ".json", ".csv"}

st.set_page_config(page_title="My Activity Lens", page_icon="📊", layout="wide")


# ---------- 데이터 로드 (캐시) ----------

@st.cache_data(show_spinner="데이터를 읽는 중…")
def load_folder(directory: str, source: str, labels: tuple, exclude: tuple) -> Dataset:
    return build_dataset(load_dir(Path(directory)), source, dict(labels), exclude)


@st.cache_data(show_spinner="업로드한 파일을 읽는 중…")
def load_uploads(files: tuple, labels: tuple, exclude: tuple) -> Dataset:
    return build_dataset(group_uploads(list(files)), "upload", dict(labels), exclude)


def has_raw_data() -> bool:
    return RAW.exists() and any(p.is_file() and p.suffix.lower() in _DATA_SUFFIXES for p in RAW.rglob("*"))


# ---------- 사이드바: 데이터 소스 ----------

with st.sidebar:
    st.title("📊 My Activity Lens")
    st.caption("Google Takeout 활동 기록 시계열 분석")
    options = ["sample", "upload"] + (["raw"] if has_raw_data() else [])
    source = st.radio("데이터 소스", options, format_func=SOURCES.get)
    files = []
    if source == "upload":
        uploaded = st.file_uploader("Takeout 파일 (zip·json·csv)", type=["zip", "json", "csv"],
                                    accept_multiple_files=True,
                                    help="zip은 파일마다, 낱개 json·csv는 한 묶음으로 처리합니다. 파일은 저장하지 않습니다.")
        files = [(f.name, f.getvalue()) for f in uploaded or []]
    exclude_text = st.text_input("제외 도메인", placeholder="example.com, mail.example.com",
                                 help="웹 방문 분석에서 뺄 도메인. 하위 도메인도 함께 빠집니다.")

exclude = tuple(sorted({d.strip() for d in exclude_text.split(",") if d.strip()}))
labels = tuple(sorted((k.removeprefix("label::"), v.strip()) for k, v in st.session_state.items()
                      if isinstance(k, str) and k.startswith("label::") and isinstance(v, str) and v.strip()))

if source == "upload":
    if not files:
        st.info("왼쪽에서 Google Takeout 파일을 업로드하세요. 내보내기 방법은 저장소의 prd.md 4.1절에 있습니다.")
        st.stop()
    ds = load_uploads(tuple(files), labels, exclude)
else:
    ds = load_folder(str(RAW if source == "raw" else SAMPLE), source, labels, exclude)

if ds.events.empty:
    st.warning("분석할 활동 기록을 찾지 못했습니다. 파일 형식(JSON)과 내용을 확인하세요.")
    st.stop()

result = next(iter(ds.results.values()))
events = ds.events
present = [s for s in SERVICE_NAMES if ds.sources.get(s) != "none"]

# ---------- 사이드바: 필터 ----------

with st.sidebar:
    st.divider()
    st.subheader("필터")
    mask = st.toggle("이름 가리기", value=False, help="화면 공유·스크린샷용. 검색어·채널·도메인·프로필 이름을 빈도 순위로 가립니다.")
    aliases = profile_aliases(events["profile"])
    first, last = events["ts_kst"].min().date(), events["ts_kst"].max().date()
    period = st.date_input("기간", value=(first, last), min_value=first, max_value=last)
    start, end = (period if isinstance(period, tuple) and len(period) == 2 else (first, last))
    services = st.multiselect("서비스", present, default=present, format_func=lambda s: service_label(s, ds.sources))
    profiles = sorted(events["profile"].astype(str).unique())
    chosen_profiles = st.multiselect("프로필", profiles, default=profiles,
                                     format_func=lambda p: aliases[p] if mask else p)
    unit = st.radio("집계 단위", list(UNITS), format_func=UNITS.get, horizontal=True)
    window = st.slider("이동평균 창 (구간 수)", 2, 60, {"D": 7, "W": 4, "M": 3}[unit])
    top_n = st.slider("Top N", 5, 30, 10)
    phase_text = st.text_area("생활 단계 (이름, 시작일)", value=REPORT_PHASES if source == "raw" else "",
                              placeholder="재직, 2025-01-01\n퇴사 후, 2026-04-01", height=110,
                              help="한 줄에 하나씩. 입력하면 차트에 경계선이 그려지고 '생활 단계' 탭이 나타납니다.")
    phases, phase_errors = parse_phases(phase_text)
    for line in phase_errors:
        st.warning(f"생활 단계 형식 오류: {line}")
    if not mask:  # 가리기 중에는 실제 프로필 이름이 보이는 입력란을 숨긴다
        with st.expander("프로필 이름 바꾸기"):
            for p in result.profiles:
                st.text_input(f"{p.source}", key=f"label::{p.source}", placeholder=p.label,
                              help=f"자동 식별: {p.label} ({p.method})")

dates = events["ts_kst"].dt.tz_localize(None).dt.normalize()
fev = events[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
             & events["service"].astype(str).isin(services)
             & events["profile"].astype(str).isin(chosen_profiles)]
if fev.empty:
    st.warning("선택한 조건에 맞는 기록이 없습니다. 필터를 바꿔 보세요.")
    st.stop()
fev = add_labels(fev, mask, aliases)
fev["service"] = fev["service"].astype(str).astype("category")
daily = F.daily_by_service(fev)
series = {s: F.resample(x, unit) for s, x in daily.items()}
outliers = {s: F.flag_outliers(x) for s, x in daily.items()} if unit == "D" else None
gaps = {s: F.find_gaps(x) for s, x in daily.items()}

# ---------- 본문 ----------

st.title("내 구글 활동 시계열 분석")
if any(ds.sources.get(s) == "sample" for s in services):
    st.caption("⚠️ 합성 샘플 데이터입니다. 실제 개인 기록이 아닙니다.")

tab_names = ["개요", "추세", "리듬", "관심사"]
has_profiles = fev.loc[fev["service"] == "yt_watch", "profile"].nunique() >= 2
has_web = "web_visit" in daily
tab_names += ["채널 비교"] * has_profiles + ["웹 방문"] * has_web + ["생활 단계"] * bool(phases) + ["심화"]
tabs = dict(zip(tab_names, st.tabs(tab_names)))

with tabs["개요"]:
    total = F.combined_daily(fev)["total"]
    busiest = total.idxmax()
    cols = st.columns(4)
    cols[0].metric("총 이벤트", f"{len(fev):,}")
    cols[1].metric("기간", f"{len(total):,}일")
    cols[1].caption(f"{total.index.min():%Y-%m-%d} ~ {total.index.max():%Y-%m-%d}")
    cols[2].metric("일평균", f"{total.mean():.1f}건")
    cols[3].metric("최다 활동일", f"{busiest:%Y-%m-%d}")
    cols[3].caption(f"{int(total.max()):,}건")

    st.subheader("서비스별 요약")
    st.dataframe(pd.DataFrame({
        service_label(s, ds.sources): {
            "시작": x.index.min().date(), "종료": x.index.max().date(), "달력 일수": len(x),
            "활동 있는 날": int((x > 0).sum()), "총 건수": int(x.sum()), "일평균": round(x.mean(), 1),
            "기록 중단 의심 구간": len(gaps[s]),
            "이상치 일수": int(F.flag_outliers(x).sum()),
        } for s, x in daily.items()
    }).T, use_container_width=True)

    left, right = st.columns(2)
    with left:
        st.subheader("데이터 품질 (파싱 통계)")
        st.dataframe(pd.DataFrame({name: asdict(s) for name, s in result.stats.items()}), use_container_width=True)
        for w in result.warnings:
            st.warning(w)
        st.caption(f"병합 중복 제거: {result.duplicates_removed:,}건")
    with right:
        st.subheader("프로필")
        st.dataframe(pd.DataFrame([{"내보내기": p.source, "프로필": aliases.get(p.label, p.label) if mask else p.label,
                                    "식별 방식": p.method} for p in result.profiles]),
                     use_container_width=True, hide_index=True)
        gap_rows = [{"서비스": service_label(s, ds.sources), "시작": g["start"].date(), "끝": g["end"].date(),
                     "일수": g["days"]} for s, t in gaps.items() for _, g in t.iterrows()]
        if gap_rows:
            st.subheader("기록 중단 의심 구간")
            st.dataframe(pd.DataFrame(gap_rows), use_container_width=True, hide_index=True)

    export = F.resample(F.combined_daily(fev), unit)
    st.download_button("집계 CSV 다운로드", export.to_csv(encoding="utf-8-sig").encode("utf-8-sig"),
                       file_name=f"activity_{UNITS[unit]}별.csv", mime="text/csv")

with tabs["추세"]:
    st.plotly_chart(charts.trend_chart(series, window, ds.sources, outliers, phases), use_container_width=True)
    if unit != "D":
        st.caption("이상치 마커는 일 단위에서만 표시합니다.")
    st.subheader(f"직전 {UNITS[unit]} 대비 변화율")
    st.plotly_chart(charts.change_chart(series, ds.sources), use_container_width=True)

with tabs["리듬"]:
    svc = st.selectbox("히트맵 서비스", list(daily), format_func=lambda s: service_label(s, ds.sources))
    st.plotly_chart(charts.heatmap_chart(F.weekday_hour_matrix(fev[fev["service"] == svc]),
                                         f"요일 × 시간대: {service_label(svc, ds.sources)}"), use_container_width=True)
    st.plotly_chart(charts.distribution_chart(fev, ds.sources), use_container_width=True)

with tabs["관심사"]:
    cols = st.columns(min(len(daily), 2))
    for i, s in enumerate(daily):
        top = F.top_n(fev, "label", top_n, service=s)
        if len(top):
            with cols[i % len(cols)]:
                st.plotly_chart(charts.top_n_chart(top, f"{service_label(s, ds.sources)} 상위 {LABEL_KINDS.get(s, '')}",
                                                   SERVICE_COLORS.get(s, "#4C78A8")), use_container_width=True)
    keywords = st.text_input("키워드 추적 (쉼표로 구분)", placeholder="파이썬, 여행",
                             help="검색어·채널·도메인 이름에 키워드가 들어간 기록의 수를 시간에 따라 봅니다.")
    kws = [k.strip() for k in keywords.split(",") if k.strip()]
    if kws:
        st.plotly_chart(charts.track_chart(fev, kws, unit), use_container_width=True)

if "채널 비교" in tabs:
    with tabs["채널 비교"]:
        watch = fev[fev["service"] == "yt_watch"]
        st.plotly_chart(charts.profile_compare_chart(watch), use_container_width=True)
        st.subheader("콘텐츠 채널 겹침")
        st.dataframe(channel_overlap(fev.assign(channel=fev["label"].where(fev["service"] == "yt_watch"))),
                     use_container_width=True, hide_index=True)

if "웹 방문" in tabs:
    with tabs["웹 방문"]:
        web = fev[fev["service"] == "web_visit"]
        st.plotly_chart(charts.domain_trend_chart(web, k=min(top_n, 8), phases=phases), use_container_width=True)
        if len(daily) >= 2:
            st.plotly_chart(charts.combined_area_chart(daily, ds.sources, phases), use_container_width=True)

if "생활 단계" in tabs:
    with tabs["생활 단계"]:
        st.plotly_chart(charts.phase_chart(daily, phases, ds.sources), use_container_width=True)
        for s, x in daily.items():
            st.subheader(service_label(s, ds.sources))
            st.dataframe(F.phase_summary(fev[fev["service"] == s], x, phases).round(1), use_container_width=True)

with tabs["심화"]:
    st.info("시계열 분해(STL)와 베이스라인 예측은 향후 계획입니다. 계획은 저장소의 future_plan.md에 있습니다.")
