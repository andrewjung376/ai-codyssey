"""개인정보가 없는 합성 Takeout 샘플 데이터를 만든다.

실제 Takeout과 같은 zip 구조·JSON 필드로 만들어, 실제 데이터와 같은 경로로 처리되게 한다.
정제 규칙(PRD 4.4)을 검증할 수 있도록 이상치, 기록 중단 구간, 광고, 삭제된 영상, 중복 레코드를 일부러 넣는다.

실행: python -m src.make_sample
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

import numpy as np

SEED = 42
START = date(2025, 10, 1)
DAYS = 365
KST = timezone(timedelta(hours=9))
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "sample"
ZIP_TIMESTAMP = (2026, 10, 22, 0, 0, 0)  # zip 내부 파일 시각 고정 (재현성)

GAP_START = date(2026, 3, 10)  # personal 프로필의 기록 중단 구간
GAP_DAYS = 10
BINGE_DAYS = {date(2025, 12, 25), date(2026, 2, 14), date(2026, 8, 15)}  # 몰아보기 급증일
BINGE_FACTOR = 5
AD_RATE = 0.03
DELETED_RATE = 0.02
VISITED_RATE = 0.10
MY_ACTIVITY_DUP_RATE = 0.30  # 내 활동 > YouTube에 중복으로 들어가는 시청 기록 비율

# 분기별 관심 검색어 (관심사 변화 분석용)
QUARTER_TOPICS = [
    ["파이썬 리스트 정렬", "pandas groupby", "파이썬 가상환경", "matplotlib 한글 폰트"],
    ["제주도 여행 코스", "항공권 특가", "여행 짐 체크리스트", "제주 맛집"],
    ["시계열 이동평균", "streamlit 배포", "plotly 히트맵", "statsmodels STL"],
    ["캠핑 장비 추천", "텐트 설치 방법", "캠핑 요리", "캠핑장 예약"],
]
COMMON_QUERIES = ["날씨", "환율", "맛집 추천", "지하철 노선도", "뉴스"]
COOKING_QUERIES = ["김치찌개 레시피", "에어프라이어 요리", "베이킹 기초", "도시락 메뉴", "칼 가는 법"]
VISITED_SITES = [
    "https://docs.python.org/3/",
    "https://pandas.pydata.org/docs/",
    "https://example.com/travel",
    "https://example.org/recipe",
]
# Chrome 방문 사이트 (URL 앞부분, 페이지 제목, 가중치). 실존 개인 정보 없음
WEB_SITES = [
    ("https://github.com/sample-user/sample-repo/blob/main/", "GitHub - sample-repo", 4),
    ("https://docs.python.org/3/library/", "Python 문서", 3),
    ("https://pandas.pydata.org/docs/reference/", "pandas 문서", 2),
    ("https://news.example.com/article/", "샘플 뉴스", 2),
    ("https://shop.example.net/item/", "샘플 쇼핑", 1),
    ("https://blog.example.org/post/", "샘플 블로그", 1),
    ("https://mail.example.com/inbox/", "받은편지함", 2),
    ("https://drive.google.com/drive/folders/", "내 드라이브", 1),
]
WEB_LOCAL_RATE = 0.03      # localhost 방문 (제외 대상)
WEB_SEARCH_RATE = 0.03     # Google 검색 결과 페이지 (search와 중복, 제외 대상)
WEB_YOUTUBE_RATE = 0.02    # YouTube 시청 페이지 (yt_watch와 중복, 제외 대상)
WEB_NO_URL_RATE = 0.01     # "Used Chrome" (URL 없음, 제외 대상)
WEB_REPEAT_RATE = 0.05     # 20초 뒤 같은 도메인 재방문 (1건으로 묶일 대상)
LOCATION_INFO = [{
    "name": "At this general area",
    "url": "https://www.google.com/maps/@?api=1&map_action=map&center=37.5,127.0&zoom=12",
    "source": "From your device",
}]


@dataclass
class ServiceConfig:
    base: float          # 평일 하루 평균 건수
    weekend: float       # 주말 배율
    slope: float         # 기간 전체 추세 (0.4 → 0.8배에서 1.2배로 증가)


@dataclass
class ProfileConfig:
    zip_name: str
    lang: str            # "en" / "ko" (title 문구 언어)
    channel_id: str
    channel_title: str
    services: dict[str, ServiceConfig]
    channels: dict[str, float]          # 콘텐츠 채널 → 선택 가중치
    weekday_peaks: dict[int, float]     # 시간 → 가중치 추가분
    weekend_peaks: dict[int, float]
    yt_queries: list[str]
    has_gap: bool
    has_binge: bool


PROFILES = [
    ProfileConfig(
        zip_name="takeout-personal.zip",
        lang="en",
        channel_id="UCsamplePersonal0000001",
        channel_title="샘플 개인 채널",
        services={
            "search": ServiceConfig(base=12, weekend=0.7, slope=0.0),
            "yt_watch": ServiceConfig(base=15, weekend=1.6, slope=0.4),
            "yt_search": ServiceConfig(base=3, weekend=1.2, slope=0.0),
            "web_visit": ServiceConfig(base=20, weekend=0.5, slope=0.2),
        },
        channels={
            "파이썬 공부 채널 A": 3, "데이터 분석 채널 B": 2, "여행 브이로그 C": 2,
            "요리 채널 D": 1, "음악 플레이리스트 E": 3, "뉴스 요약 F": 2,
        },
        weekday_peaks={9: 0.6, 10: 0.8, 11: 0.6, 13: 0.4, 20: 1.0, 21: 1.4, 22: 1.4, 23: 0.8},
        weekend_peaks={11: 0.6, 14: 0.8, 15: 0.8, 16: 0.6, 21: 1.0, 22: 1.0},
        yt_queries=[q for topics in QUARTER_TOPICS for q in topics],
        has_gap=True,
        has_binge=True,
    ),
    ProfileConfig(
        zip_name="takeout-brand.zip",
        lang="ko",
        channel_id="UCsampleBrand0000000001",
        channel_title="샘플 요리 채널",
        services={
            "yt_watch": ServiceConfig(base=6, weekend=1.3, slope=0.2),
            "yt_search": ServiceConfig(base=2, weekend=1.0, slope=0.0),
        },
        channels={
            "요리 채널 D": 3, "베이킹 채널 G": 2, "주방 도구 리뷰 H": 1,
            "레시피 모음 I": 2, "음악 플레이리스트 E": 1,
        },
        weekday_peaks={11: 1.0, 12: 1.2, 17: 1.0, 18: 1.4, 19: 0.8},
        weekend_peaks={10: 1.0, 11: 1.2, 16: 0.8, 17: 1.0},
        yt_queries=COOKING_QUERIES,
        has_gap=False,
        has_binge=False,
    ),
]

_ID_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def _hour_weights(peaks: dict[int, float]) -> np.ndarray:
    weights = np.full(24, 0.15)
    weights[1:7] = 0.02  # 새벽 수면 시간
    for hour, extra in peaks.items():
        weights[hour] += extra
    return weights / weights.sum()


def _video_id(rng: np.random.Generator) -> str:
    return "".join(rng.choice(list(_ID_ALPHABET), size=11))


def _iso_utc(dt_kst: datetime, rng: np.random.Generator) -> str:
    """Takeout과 같은 UTC ISO 8601 문자열. 일부는 소수점 초 없이 만든다."""
    dt = dt_kst.astimezone(timezone.utc)
    if rng.random() < 0.1:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _title(lang: str, kind: str, text: str) -> str:
    if lang == "ko":
        return {
            "watch": f"{text} 을(를) 시청했습니다.",
            "search": f"{text}을(를) 검색했습니다.",
            "visit": f"{text}을(를) 방문했습니다.",
        }[kind]
    return {"watch": f"Watched {text}", "search": f"Searched for {text}", "visit": f"Visited {text}"}[kind]


def _search_query(rng: np.random.Generator, day_index: int) -> str:
    quarter = min(3, day_index * 4 // DAYS)
    pool = QUARTER_TOPICS[quarter] if rng.random() < 0.7 else COMMON_QUERIES
    return str(rng.choice(pool))


def _generate_profile(cfg: ProfileConfig, rng: np.random.Generator) -> dict[str, list[dict]]:
    """프로필 하나의 레코드를 서비스별로 만든다. 반환: {"search": [...], "yt_watch": [...], "yt_search": [...]}"""
    videos = {
        ch: [(_video_id(rng), f"{ch} - 에피소드 {n}") for n in range(1, 61)]
        for ch in cfg.channels
    }
    channel_urls = {ch: f"https://www.youtube.com/channel/UC{_video_id(rng)}" for ch in cfg.channels}
    channel_names = list(cfg.channels)
    channel_p = np.array(list(cfg.channels.values()), dtype=float)
    channel_p /= channel_p.sum()
    weekday_w, weekend_w = _hour_weights(cfg.weekday_peaks), _hour_weights(cfg.weekend_peaks)

    records: dict[str, list[dict]] = {svc: [] for svc in cfg.services}
    for i in range(DAYS):
        day = START + timedelta(days=i)
        if cfg.has_gap and GAP_START <= day < GAP_START + timedelta(days=GAP_DAYS):
            continue
        weekend = day.weekday() >= 5
        progress = i / (DAYS - 1)
        for svc, scfg in cfg.services.items():
            lam = scfg.base * (scfg.weekend if weekend else 1.0) * (1 + scfg.slope * (progress - 0.5))
            if cfg.has_binge and svc == "yt_watch" and day in BINGE_DAYS:
                lam *= BINGE_FACTOR
            hours = rng.choice(24, size=rng.poisson(lam), p=weekend_w if weekend else weekday_w)
            for hour in hours:
                ts = datetime(day.year, day.month, day.day, int(hour), int(rng.integers(60)),
                              int(rng.integers(60)), int(rng.integers(1_000_000)), tzinfo=KST)
                rec = _make_record(cfg, svc, ts, i, rng, videos, channel_urls, channel_names, channel_p)
                records[svc].append(rec)
                if svc == "web_visit" and rec.get("titleUrl") and rng.random() < WEB_REPEAT_RATE:
                    records[svc].append({**rec, "time": _iso_utc(ts + timedelta(seconds=20), rng)})

    for svc in records:  # Takeout은 최신 기록이 먼저 나온다
        records[svc].sort(key=lambda r: r["time"], reverse=True)
    return records


def _make_record(cfg, svc, ts, day_index, rng, videos, channel_urls, channel_names, channel_p) -> dict:
    time = _iso_utc(ts, rng)
    if svc == "search":
        if rng.random() < VISITED_RATE:
            site = str(rng.choice(VISITED_SITES))
            return {
                "header": "Search", "title": _title(cfg.lang, "visit", site),
                "titleUrl": f"https://www.google.com/url?q={quote_plus(site)}&usg=AOvVaw0sample",
                "time": time, "products": ["Search"], "activityControls": ["Web & App Activity"],
                "locationInfos": LOCATION_INFO,
            }
        query = _search_query(rng, day_index)
        return {
            "header": "Search", "title": _title(cfg.lang, "search", query),
            "titleUrl": f"https://www.google.com/search?q={quote_plus(query)}",
            "time": time, "products": ["Search"], "activityControls": ["Web & App Activity"],
            "locationInfos": LOCATION_INFO,
        }

    if svc == "web_visit":
        return _make_web_record(cfg, time, rng)

    if svc == "yt_search":
        query = str(rng.choice(cfg.yt_queries))
        return {
            "header": "YouTube", "title": _title(cfg.lang, "search", query),
            "titleUrl": f"https://www.youtube.com/results?search_query={quote_plus(query)}",
            "time": time, "products": ["YouTube"], "activityControls": ["YouTube search history"],
        }

    # yt_watch
    roll = rng.random()
    if roll < AD_RATE:
        vid = _video_id(rng)
        return {
            "header": "YouTube", "title": _title(cfg.lang, "watch", f"광고 영상 {vid[:4]}"),
            "titleUrl": f"https://www.youtube.com/watch?v={vid}",
            "subtitles": [{"name": "샘플 광고주", "url": "https://www.youtube.com/channel/UCsampleAdvertiser00001"}],
            "time": time, "products": ["YouTube"], "activityControls": ["YouTube watch history"],
            "details": [{"name": "From Google Ads"}],
        }
    if roll < AD_RATE + DELETED_RATE:
        url = f"https://www.youtube.com/watch?v={_video_id(rng)}"
        return {
            "header": "YouTube", "title": _title(cfg.lang, "watch", url), "titleUrl": url,
            "time": time, "products": ["YouTube"], "activityControls": ["YouTube watch history"],
        }
    channel = str(rng.choice(channel_names, p=channel_p))
    vid, video_title = videos[channel][int(rng.integers(len(videos[channel])))]
    return {
        "header": "YouTube", "title": _title(cfg.lang, "watch", video_title),
        "titleUrl": f"https://www.youtube.com/watch?v={vid}",
        "subtitles": [{"name": channel, "url": channel_urls[channel]}],
        "time": time, "products": ["YouTube"], "activityControls": ["YouTube watch history"],
    }


def _make_web_record(cfg: ProfileConfig, time: str, rng: np.random.Generator) -> dict:
    """내 활동 > Chrome 형식. 실제 내보내기처럼 titleUrl을 google.com/url?q= 로 감싼다."""
    base = {"time": time, "products": ["Chrome"], "activityControls": ["Web & App Activity"]}
    roll = rng.random()
    if roll < WEB_NO_URL_RATE:
        return {"header": "Chrome", "title": "Used Chrome", **base}
    roll -= WEB_NO_URL_RATE
    if roll < WEB_LOCAL_RATE:
        url, title = "http://localhost:8501/", "Streamlit"
    elif roll < WEB_LOCAL_RATE + WEB_SEARCH_RATE:
        query = str(rng.choice(COMMON_QUERIES))
        url, title = f"https://www.google.com/search?q={quote_plus(query)}", f"{query} - Google 검색"
    elif roll < WEB_LOCAL_RATE + WEB_SEARCH_RATE + WEB_YOUTUBE_RATE:
        url, title = f"https://www.youtube.com/watch?v={_video_id(rng)}", "YouTube"
    else:
        weights = np.array([w for *_, w in WEB_SITES], dtype=float)
        prefix, title, _ = WEB_SITES[int(rng.choice(len(WEB_SITES), p=weights / weights.sum()))]
        url = f"{prefix}{int(rng.integers(1, 200))}"
    host = url.split("/")[2].removeprefix("www.")
    return {
        "header": host, "title": _title(cfg.lang, "visit", title),
        "titleUrl": f"https://www.google.com/url?q={quote_plus(url)}&usg=AOvVaw0sample", **base,
    }


def _channel_csv(cfg: ProfileConfig) -> str:
    if cfg.lang == "ko":
        header = ["채널 ID", "채널 제목(원본)", "채널 공개 상태"]
        row = [cfg.channel_id, cfg.channel_title, "공개"]
    else:
        header = ["Channel ID", "Channel Title (Original)", "Channel Visibility"]
        row = [cfg.channel_id, cfg.channel_title, "Public"]
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerow(row)
    return buf.getvalue()


def _zip_layout(cfg: ProfileConfig, records: dict[str, list[dict]], rng: np.random.Generator) -> dict[str, str]:
    """zip 내부 경로 → 파일 내용. 계정 언어에 따라 폴더 이름이 다른 실제 Takeout을 흉내 낸다."""
    def dump(data):
        return json.dumps(data, ensure_ascii=False, indent=2)

    if cfg.lang == "ko":
        yt = "Takeout/YouTube 및 YouTube Music"
        files = {
            f"{yt}/기록/시청 기록.json": dump(records["yt_watch"]),
            f"{yt}/기록/검색 기록.json": dump(records["yt_search"]),
            f"{yt}/채널/채널.csv": _channel_csv(cfg),
        }
    else:
        yt = "Takeout/YouTube and YouTube Music"
        files = {
            f"{yt}/history/watch-history.json": dump(records["yt_watch"]),
            f"{yt}/history/search-history.json": dump(records["yt_search"]),
            f"{yt}/channels/channel.csv": _channel_csv(cfg),
        }
    if "search" in records:
        files["Takeout/My Activity/Search/MyActivity.json"] = dump(records["search"])
        # 내 활동 > YouTube에는 시청 기록 일부가 똑같이 들어 있다 (중복 제거 검증용)
        dup = [r for r in records["yt_watch"] if rng.random() < MY_ACTIVITY_DUP_RATE]
        files["Takeout/My Activity/YouTube/MyActivity.json"] = dump(dup)
    if "web_visit" in records:
        files["Takeout/My Activity/Chrome/MyActivity.json"] = dump(records["web_visit"])
    return files


def _write_zip(path: Path, files: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in files.items():
            info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, text.encode("utf-8"))


def build(out_dir: Path = OUT_DIR, seed: int = SEED) -> list[Path]:
    """샘플 zip을 만들고 경로 목록을 돌려준다."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    paths = []
    for cfg in PROFILES:
        records = _generate_profile(cfg, rng)
        path = out_dir / cfg.zip_name
        _write_zip(path, _zip_layout(cfg, records, rng))
        paths.append(path)
    return paths


if __name__ == "__main__":
    for p in build():
        print(f"생성: {p} ({p.stat().st_size / 1024:.0f} KB)")
