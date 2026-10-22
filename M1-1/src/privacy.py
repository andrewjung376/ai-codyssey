"""리포트·이미지에 실을 실제 데이터의 이름(도메인·채널·검색어) 가리기 (NFR-03, NFR-10).

공개해도 되는 이름은 사용자가 doc/domain_review.md, doc/channel_review.md에서 직접 체크한다.
doc/는 커밋되지 않는다.
- 검토 전(체크 목록 없음): 모든 이름을 "도메인 1, 도메인 2…"처럼 빈도 순위로 가린다
- 검토 후: 체크한 이름만 실명으로 두고 나머지는 "기타 도메인"으로 묶는다
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DOMAIN_REVIEW_PATH = ROOT / "doc" / "domain_review.md"
CHANNEL_REVIEW_PATH = ROOT / "doc" / "channel_review.md"
_ITEM = re.compile(r"^- \[(?P<mark>[ xX])\] `(?P<name>[^`]+)`")


def read_public_names(path: Path = DOMAIN_REVIEW_PATH) -> set[str] | None:
    """체크([x])한 이름 집합. 검토 파일이 없거나 하나도 체크하지 않았으면 None(검토 전)."""
    if not path.exists():
        return None
    names = {m["name"] for line in path.read_text(encoding="utf-8").splitlines()
             if (m := _ITEM.match(line.strip())) and m["mark"] in "xX"}
    return names or None


def write_review(values: pd.Series, path: Path = DOMAIN_REVIEW_PATH, n: int = 30, kind: str = "도메인") -> Path:
    """상위 n개 이름을 체크 목록으로 쓴다. 기존 파일에서 체크한 항목은 유지한다."""
    checked = read_public_names(path) or set()
    counts = values.dropna().value_counts().head(n)
    lines = [
        f"# 공개 {kind} 검토 (로컬 전용, 커밋되지 않음)",
        "",
        f"리포트와 그래프에 실명으로 실어도 되는 {kind}만 `[ ]`를 `[x]`로 바꾸세요.",
        f"체크하지 않은 {kind}는 \"기타 {kind}\"로 묶입니다. 노트북을 다시 실행하면 반영됩니다.",
        "",
        *[f"- [{'x' if name in checked else ' '}] `{name}` ({count:,}건)" for name, count in counts.items()],
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def mask_labels(values: pd.Series, public: set[str] | None, kind: str = "도메인") -> pd.Series:
    """values의 이름을 가린 Series (index 유지)."""
    if public is None:
        ranks = {name: i for i, name in enumerate(values.dropna().value_counts().index, start=1)}
        return values.map(lambda v: f"{kind} {ranks[v]}" if v in ranks else v)
    return values.map(lambda v: v if pd.isna(v) or v in public else f"기타 {kind}")
