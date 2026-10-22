"""Takeout 활동 레코드를 events DataFrame(PRD 4.3)으로 바꾸고 정제 규칙(PRD 4.4)을 적용한다.

서비스 종류는 언어별 문구 대신 `titleUrl` 도메인으로 판별한다.
- google.*/search → search(searched),  google.*/url → search(visited)
- youtube.com/watch → yt_watch,  youtube.com/results → yt_search
`locationInfos` 등 쓰지 않는 필드는 읽지 않고 버린다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import pandas as pd

KST = "Asia/Seoul"
SEARCH_PROFILE = "personal"  # Google 검색 기록은 개인 계정에만 있다 (PRD 4.5)
DELETED_VIDEO = "(삭제된 영상)"
EVENT_COLUMNS = ["ts_kst", "profile", "profile_id", "service", "activity", "text", "channel", "video_id"]

# title에서 활동 문구를 떼어 내는 패턴 (영어·한국어)
_TITLE_PATTERNS = [
    re.compile(r"^(?:Watched|Searched for|Visited)\s+(?P<text>.+)$", re.S),
    re.compile(r"^(?P<text>.+?)\s*을\(를\)\s*(?:시청|검색|방문)했습니다\.?$", re.S),
]
_WATCH_TITLE = re.compile(r"^Watched\s|시청했습니다\.?$")
_AD_MARKERS = ("Google Ads", "Google 광고")


@dataclass
class ParseStats:
    total: int = 0
    parsed: int = 0
    ads_removed: int = 0
    deleted_videos: int = 0
    unsupported: int = 0     # 분석 대상이 아닌 활동 (구독, 지도 등)
    invalid_time: int = 0


def strip_title(title: str) -> str:
    for pattern in _TITLE_PATTERNS:
        m = pattern.match(title.strip())
        if m:
            return m.group("text").strip()
    return title.strip()


def classify(record: dict) -> tuple[str, str] | None:
    """(service, activity)를 돌려준다. 분석 대상이 아니면 None."""
    url = record.get("titleUrl") or ""
    parsed = urlparse(url)
    host, path = parsed.netloc.lower(), parsed.path
    if host.endswith("youtube.com"):
        if path == "/watch":
            return "yt_watch", "watched"
        if path == "/results":
            return "yt_search", "searched"
        return None
    if host.startswith(("www.google.", "google.")):
        if path == "/search":
            return "search", "searched"
        if path == "/url":
            return "search", "visited"
        return None
    # 영상이 완전히 삭제되면 titleUrl 없이 title만 남는다
    if not url and "YouTube" in record.get("header", "") and _WATCH_TITLE.search(record.get("title", "")):
        return "yt_watch", "watched"
    return None


def _query_param(url: str, key: str) -> str | None:
    values = parse_qs(urlparse(url).query).get(key)
    return values[0].strip() if values else None


def _is_ad(record: dict) -> bool:
    return any(
        marker in (d.get("name") or "")
        for d in record.get("details") or []
        for marker in _AD_MARKERS
    )


def parse_records(records: list[dict], profile: str, profile_id: str | None = None) -> tuple[pd.DataFrame, ParseStats]:
    """레코드 목록을 events DataFrame으로 바꾼다. YouTube 기록에는 profile을, 검색 기록에는 SEARCH_PROFILE을 붙인다."""
    stats = ParseStats(total=len(records))
    rows = []
    for rec in records:
        if not isinstance(rec, dict):
            stats.unsupported += 1
            continue
        kind = classify(rec)
        if kind is None:
            stats.unsupported += 1
            continue
        if _is_ad(rec):
            stats.ads_removed += 1
            continue
        service, activity = kind
        url = rec.get("titleUrl") or ""
        title_text = strip_title(rec.get("title") or "")
        channel = video_id = None

        if service == "search":
            text = _query_param(url, "q") or title_text
        elif service == "yt_search":
            text = _query_param(url, "search_query") or title_text
        else:
            video_id = _query_param(url, "v")
            subtitles = rec.get("subtitles") or []
            if not subtitles and (not url or title_text.startswith("http") or "youtube.com/watch" in title_text):
                text = DELETED_VIDEO
                stats.deleted_videos += 1
            else:
                text = title_text
                channel = (subtitles[0].get("name") or None) if subtitles else None

        is_search = service == "search"
        rows.append({
            "time": rec.get("time"),
            "profile": SEARCH_PROFILE if is_search else profile,
            "profile_id": None if is_search else profile_id,
            "service": service,
            "activity": activity,
            "text": text,
            "channel": channel,
            "video_id": video_id,
        })

    df = pd.DataFrame(rows, columns=["time", *EVENT_COLUMNS[1:]])
    ts = pd.to_datetime(df["time"], utc=True, format="ISO8601", errors="coerce")
    stats.invalid_time = int(ts.isna().sum())
    df.insert(0, "ts_kst", ts.dt.tz_convert(KST))
    df = df.drop(columns="time").dropna(subset=["ts_kst"]).reset_index(drop=True)
    stats.parsed = len(df)
    return df, stats
