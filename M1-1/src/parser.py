"""Takeout 활동 레코드를 events DataFrame(PRD 4.3)으로 바꾸고 정제 규칙(PRD 4.4)을 적용한다.

서비스 종류는 언어별 문구 대신 `products`와 `titleUrl`로 판별한다.
- products에 Chrome → web_visit (titleUrl의 google.com/url 래퍼를 풀어 도메인만 남김)
- google.*/search → search(searched),  google.*/url → search(visited)
- youtube.com/watch → yt_watch,  youtube.com/results → yt_search
`locationInfos`, 웹 방문의 URL 경로·페이지 제목 등 쓰지 않는 정보는 읽지 않고 버린다.
"""
from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pandas as pd

KST = "Asia/Seoul"
PERSONAL_PROFILE = "personal"  # Google 검색·Chrome 기록은 개인 계정에만 있다 (PRD 4.5)
DELETED_VIDEO = "(삭제된 영상)"
EVENT_COLUMNS = ["ts_kst", "profile", "profile_id", "service", "activity", "text", "channel", "video_id", "domain"]
REPEAT_VISIT_SECONDS = 60  # 같은 도메인을 이 시간 안에 다시 방문하면 1건으로 묶는다

# title에서 활동 문구를 떼어 내는 패턴 (영어·한국어)
_TITLE_PATTERNS = [
    re.compile(r"^(?:Watched|Searched for|Visited)\s+(?P<text>.+)$", re.S),
    re.compile(r"^(?P<text>.+?)\s*을\(를\)\s*(?:시청|검색|방문)했습니다\.?$", re.S),
]
_WATCH_TITLE = re.compile(r"^Watched\s|시청했습니다\.?$")
_AD_MARKERS = ("Google Ads", "Google 광고")
_GOOGLE_HOSTS = ("www.google.", "google.")


@dataclass
class ParseStats:
    total: int = 0
    parsed: int = 0
    ads_removed: int = 0
    deleted_videos: int = 0
    unsupported: int = 0     # 분석 대상이 아닌 활동 (구독, 지도, URL 없는 Chrome 기록 등)
    invalid_time: int = 0
    web_excluded: int = 0    # 내부·로컬 주소, 검색·YouTube와 겹치는 방문, 새로고침
    web_blocked: int = 0     # 사용자 제외 목록
    web_repeats_merged: int = 0
    chrome_skipped: int = 0  # BrowserHistory가 있어 쓰지 않은 내 활동 > Chrome 레코드

    def __add__(self, other: ParseStats) -> ParseStats:
        return ParseStats(**{f.name: getattr(self, f.name) + getattr(other, f.name) for f in fields(self)})


def strip_title(title: str) -> str:
    for pattern in _TITLE_PATTERNS:
        m = pattern.match(title.strip())
        if m:
            return m.group("text").strip()
    return title.strip()


def is_chrome_record(record: dict) -> bool:
    return "Chrome" in (record.get("products") or [])


def classify(record: dict) -> tuple[str, str] | None:
    """(service, activity)를 돌려준다. 분석 대상이 아니면 None."""
    url = record.get("titleUrl") or ""
    if is_chrome_record(record):
        return ("web_visit", "visited") if url else None  # "Chrome을 사용함"처럼 URL 없는 기록은 제외
    parsed = urlparse(url)
    host, path = parsed.netloc.lower(), parsed.path
    if host.endswith("youtube.com"):
        if path == "/watch":
            return "yt_watch", "watched"
        if path == "/results":
            return "yt_search", "searched"
        return None
    if host.startswith(_GOOGLE_HOSTS):
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


def _is_local_host(host: str) -> bool:
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local


def web_domain(url: str) -> str | None:
    """방문 URL에서 도메인만 뽑는다. 분석에서 제외할 주소면 None (PRD 4.4)."""
    parsed = urlparse(url)
    if (parsed.hostname or "").startswith(_GOOGLE_HOSTS) and parsed.path == "/url":
        target = _query_param(url, "q") or _query_param(url, "url")
        if not target:
            return None
        parsed = urlparse(target)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in ("http", "https") or not host or _is_local_host(host):
        return None
    if host.startswith(_GOOGLE_HOSTS) and parsed.path == "/search":
        return None  # search 서비스와 중복
    if host.endswith("youtube.com") and parsed.path in ("/watch", "/results"):
        return None  # yt 서비스와 중복
    return host.removeprefix("www.")


def _is_blocked(domain: str, exclude_domains: tuple[str, ...]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in exclude_domains)


def _normalize_excludes(exclude_domains) -> tuple[str, ...]:
    return tuple(d.strip().lower().removeprefix("www.") for d in exclude_domains or () if d.strip())


def _is_ad(record: dict) -> bool:
    return any(
        marker in (d.get("name") or "")
        for d in record.get("details") or []
        for marker in _AD_MARKERS
    )


def _web_row(time, domain: str, activity: str = "visited") -> dict:
    return {"time": time, "profile": PERSONAL_PROFILE, "profile_id": None, "service": "web_visit",
            "activity": activity, "text": domain, "channel": None, "video_id": None, "domain": domain}


def parse_records(records: list[dict], profile: str, profile_id: str | None = None,
                  exclude_domains=(), skip_chrome: bool = False) -> tuple[pd.DataFrame, ParseStats]:
    """레코드 목록을 events DataFrame으로 바꾼다.

    YouTube 기록에는 profile을, 검색·Chrome 기록에는 PERSONAL_PROFILE을 붙인다.
    skip_chrome: BrowserHistory를 대신 쓸 때 내 활동 > Chrome 레코드를 건너뛴다.
    """
    exclude_domains = _normalize_excludes(exclude_domains)
    stats = ParseStats(total=len(records))
    rows = []
    for rec in records:
        if not isinstance(rec, dict):
            stats.unsupported += 1
            continue
        if skip_chrome and is_chrome_record(rec):
            stats.chrome_skipped += 1
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

        if service == "web_visit" or (service == "search" and activity == "visited"):
            domain = web_domain(url)
            if domain is None:
                stats.web_excluded += 1
                continue
            if _is_blocked(domain, exclude_domains):
                stats.web_blocked += 1
                continue
            row = _web_row(rec.get("time"), domain)
            if service == "search":  # 검색 결과에서 방문: 검색 서비스로 두되 도메인만 남긴다
                row["service"] = "search"
            rows.append(row)
            continue

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
            "profile": PERSONAL_PROFILE if is_search else profile,
            "profile_id": None if is_search else profile_id,
            "service": service,
            "activity": activity,
            "text": text,
            "channel": channel,
            "video_id": video_id,
            "domain": None,
        })
    return _finalize(rows, stats)


def parse_browser_history(items: list[dict], exclude_domains=()) -> tuple[pd.DataFrame, ParseStats]:
    """Chrome > 방문 기록(BrowserHistory JSON의 `Browser History` 목록)을 웹 방문 이벤트로 바꾼다."""
    exclude_domains = _normalize_excludes(exclude_domains)
    stats = ParseStats(total=len(items))
    rows = []
    for item in items:
        if not isinstance(item, dict) or not item.get("url") or item.get("time_usec") is None:
            stats.unsupported += 1
            continue
        transition = str(item.get("page_transition") or "").upper()
        domain = web_domain(item["url"])
        if "RELOAD" in transition or domain is None:
            stats.web_excluded += 1
            continue
        if _is_blocked(domain, exclude_domains):
            stats.web_blocked += 1
            continue
        try:
            time = datetime.fromtimestamp(int(item["time_usec"]) / 1_000_000, tz=timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            time = None
        rows.append(_web_row(time, domain, "typed" if "TYPED" in transition else "visited"))
    return _finalize(rows, stats)


def _finalize(rows: list[dict], stats: ParseStats) -> tuple[pd.DataFrame, ParseStats]:
    df = pd.DataFrame(rows, columns=["time", *EVENT_COLUMNS[1:]])
    ts = pd.to_datetime(df["time"], utc=True, format="ISO8601", errors="coerce")
    stats.invalid_time = int(ts.isna().sum())
    df.insert(0, "ts_kst", ts.dt.tz_convert(KST))
    df = df.drop(columns="time").dropna(subset=["ts_kst"])
    df, stats.web_repeats_merged = _merge_repeat_visits(df)
    stats.parsed = len(df)
    return df.reset_index(drop=True), stats


def _merge_repeat_visits(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """웹 방문 중 같은 도메인의 직전 방문과 REPEAT_VISIT_SECONDS 안에 있는 기록을 뺀다."""
    web = df["service"] == "web_visit"
    if not web.any():
        return df, 0
    visits = df[web].sort_values("ts_kst")
    gap = visits.groupby("domain")["ts_kst"].diff()
    repeat_index = visits.index[gap <= pd.Timedelta(seconds=REPEAT_VISIT_SECONDS)]
    return df.drop(index=repeat_index), len(repeat_index)
