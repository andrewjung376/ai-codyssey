"""프로필(내 채널) 식별, 여러 내보내기 병합·중복 제거, 프로필 간 비교 (PRD 4.5).

시청 기록에는 시청한 내 채널 정보가 없으므로, 내보내기(파일) 단위로 프로필을 붙인다.
식별 순서: channel.csv의 채널명 → 파일 이름 → unknown-N
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import PurePath

import pandas as pd

from .loader import TakeoutExport
from .parser import EVENT_COLUMNS, ParseStats, parse_browser_history, parse_records

DEDUP_KEY = ["profile", "service", "ts_kst", "text"]
# Takeout 기본 파일 이름(takeout-20261022T061522Z-001)은 프로필 이름으로 쓸 수 없다
_DEFAULT_TAKEOUT_NAME = re.compile(r"^takeout-\d{8}T\d{6}Z?(-\d+)?$", re.I)


@dataclass
class Profile:
    label: str
    profile_id: str | None
    method: str   # "channel.csv" / "filename" / "unknown" / "user"
    source: str   # 내보내기 파일 이름


@dataclass
class MergeResult:
    events: pd.DataFrame
    profiles: list[Profile]
    stats: dict[str, ParseStats]          # 내보내기 이름 → 파싱 통계
    duplicates_removed: int
    warnings: list[str] = field(default_factory=list)


def identify_profile(export: TakeoutExport, unknown_index: int = 1) -> Profile:
    if export.channel and export.channel.get("title"):
        return Profile(export.channel["title"], export.channel.get("id") or None, "channel.csv", export.name)
    stem = PurePath(export.name).stem
    if stem and not _DEFAULT_TAKEOUT_NAME.match(stem):
        return Profile(stem, None, "filename", export.name)
    return Profile(f"unknown-{unknown_index}", None, "unknown", export.name)


def build_events(exports: list[TakeoutExport], labels: dict[str, str] | None = None,
                 exclude_domains=()) -> MergeResult:
    """내보내기 여러 개를 하나의 events DataFrame으로 합친다.

    labels: {내보내기 이름: 사용자가 정한 프로필 라벨}. 자동 식별 결과보다 우선한다 (FR-15).
    exclude_domains: 웹 방문 분석에서 뺄 도메인 (하위 도메인 포함, FR-20).
    BrowserHistory가 하나라도 있으면 내 활동 > Chrome 레코드는 쓰지 않는다 (소스 중복 방지).
    """
    labels = labels or {}
    use_browser_history = any(e.browser_history for e in exports)
    profiles, stats, frames, warnings = [], {}, [], []
    seen: dict[str, str] = {}  # 프로필 키 → 처음 나온 내보내기 이름
    unknown_index = 1

    for export in exports:
        profile = identify_profile(export, unknown_index)
        if profile.method == "unknown":
            unknown_index += 1
        if export.name in labels:
            profile.label, profile.method = labels[export.name], "user"
        key = profile.profile_id or profile.label
        if key in seen:
            warnings.append(
                f"'{export.name}'은(는) '{seen[key]}'와 같은 프로필({profile.label})입니다. 합친 뒤 중복을 제거했습니다."
            )
        else:
            seen[key] = export.name
        profiles.append(profile)

        records = [r for recs in export.activity_files.values() for r in recs]
        df, stats[export.name] = parse_records(records, profile.label, profile.profile_id,
                                               exclude_domains, skip_chrome=use_browser_history)
        frames.append(df)
        history = [r for recs in export.browser_history.values() for r in recs]
        if history:
            df, history_stats = parse_browser_history(history, exclude_domains)
            stats[export.name] += history_stats
            frames.append(df)

    frames = [f for f in frames if not f.empty]
    events = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=EVENT_COLUMNS)
    before = len(events)
    events = events.drop_duplicates(subset=DEDUP_KEY).sort_values("ts_kst").reset_index(drop=True)
    for col in ("profile", "service", "activity"):
        events[col] = events[col].astype("category")
    return MergeResult(events, profiles, stats, before - len(events), warnings)


def channel_overlap(events: pd.DataFrame) -> pd.DataFrame:
    """프로필 쌍마다 공통 콘텐츠 채널 수와 Jaccard 지수 (FR-17)."""
    watched = events[(events["service"] == "yt_watch") & events["channel"].notna()]
    sets = {p: set(g["channel"]) for p, g in watched.groupby("profile", observed=True)}
    rows = []
    for a, b in combinations(sorted(sets), 2):
        union = sets[a] | sets[b]
        common = sets[a] & sets[b]
        rows.append({
            "profile_a": a, "profile_b": b, "common": len(common),
            "jaccard": len(common) / len(union) if union else 0.0,
            "common_channels": sorted(common),
        })
    return pd.DataFrame(rows, columns=["profile_a", "profile_b", "common", "jaccard", "common_channels"])
