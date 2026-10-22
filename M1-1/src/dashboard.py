"""대시보드(app.py) 보조 함수. Streamlit 없이 테스트할 수 있도록 분리했다."""
from __future__ import annotations

import pandas as pd

from . import privacy

LABEL_KINDS = {"search": "검색어", "yt_search": "YouTube 검색어", "yt_watch": "채널", "web_visit": "도메인"}


def parse_phases(text: str) -> tuple[list[tuple[str, str]], list[str]]:
    """'이름, YYYY-MM-DD' 줄 목록을 [(이름, 날짜)]로 바꾼다. 잘못된 줄은 오류 목록으로 돌려준다."""
    phases, errors = [], []
    for line in text.splitlines():
        if not line.strip():
            continue
        name, _, day = line.rpartition(",")
        try:
            start = pd.Timestamp(day.strip()).strftime("%Y-%m-%d")
        except ValueError:
            start = None
        if not name.strip() or start is None:
            errors.append(line)
        else:
            phases.append((name.strip(), start))
    return sorted(set(phases), key=lambda p: p[1]), errors


def profile_aliases(profiles: pd.Series) -> dict[str, str]:
    """프로필 이름 → "프로필 1, 2…" (기록이 많은 순)."""
    return {p: f"프로필 {i}" for i, p in enumerate(profiles.astype(str).value_counts().index, start=1)}


def add_labels(ev: pd.DataFrame, mask: bool, aliases: dict[str, str] | None = None) -> pd.DataFrame:
    """화면에 보일 이름(label): 검색어·채널(YouTube 시청)·도메인. mask면 빈도 순위 이름으로 가린다.

    aliases: 프로필 가림 이름. 사이드바와 같은 번호를 쓰도록 전체 데이터 기준으로 넘긴다.
    """
    ev = ev.copy()
    ev["label"] = ev["text"].astype("object")
    watch = ev["service"] == "yt_watch"
    ev.loc[watch, "label"] = ev.loc[watch, "channel"]
    if mask:
        for svc, kind in LABEL_KINDS.items():
            rows = ev["service"] == svc
            if rows.any():
                ev.loc[rows, "label"] = privacy.mask_labels(ev.loc[rows, "label"], None, kind)
        names = aliases or profile_aliases(ev["profile"])
        ev["profile"] = ev["profile"].astype(str).map(names).astype("category")
    return ev
