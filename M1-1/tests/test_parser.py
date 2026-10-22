"""parser·loader·profiles 단위 테스트 (직접 만든 소량 레코드)."""
import json

from urllib.parse import quote_plus

from src.loader import TakeoutExport, load_takeout
from src.parser import (DELETED_VIDEO, PERSONAL_PROFILE, classify, parse_browser_history, parse_records,
                        strip_title, web_domain)
from src.profiles import build_events, identify_profile


def watch(title, vid="abc", channel="채널 A", time="2026-01-01T03:00:00.000Z", **extra):
    rec = {"header": "YouTube", "title": title, "titleUrl": f"https://www.youtube.com/watch?v={vid}", "time": time}
    if channel:
        rec["subtitles"] = [{"name": channel, "url": "https://www.youtube.com/channel/UCx"}]
    rec.update(extra)
    return rec


def test_utc_to_kst_crosses_date_boundary():
    df, _ = parse_records([watch("Watched 영상", time="2026-01-01T15:30:00.000Z")], "p")
    ts = df.loc[0, "ts_kst"]
    assert (ts.year, ts.month, ts.day, ts.hour, ts.minute) == (2026, 1, 2, 0, 30)
    assert str(ts.tz) == "Asia/Seoul"


def test_time_without_fraction_is_parsed():
    df, stats = parse_records([watch("Watched 영상", time="2026-01-01T03:00:00Z")], "p")
    assert stats.invalid_time == 0 and len(df) == 1


def test_invalid_time_is_counted_and_dropped():
    df, stats = parse_records([watch("Watched 영상", time="not-a-time")], "p")
    assert stats.invalid_time == 1 and df.empty


def test_strip_title_english_and_korean():
    assert strip_title("Watched 파이썬 강의") == "파이썬 강의"
    assert strip_title("Searched for pandas groupby") == "pandas groupby"
    assert strip_title("파이썬 강의 을(를) 시청했습니다.") == "파이썬 강의"
    assert strip_title("김치찌개 레시피을(를) 검색했습니다.") == "김치찌개 레시피"


def test_classify_by_url():
    assert classify({"titleUrl": "https://www.google.com/search?q=x"}) == ("search", "searched")
    assert classify({"titleUrl": "https://www.google.com/url?q=https://a.com"}) == ("search", "visited")
    assert classify({"titleUrl": "https://www.youtube.com/results?search_query=x"}) == ("yt_search", "searched")
    assert classify({"titleUrl": "https://www.google.com/maps/place/x"}) is None
    assert classify({"header": "YouTube", "title": "Subscribed to 채널"}) is None


def test_search_query_from_url_and_personal_profile():
    rec = {"header": "Search", "title": "Searched for 다른 문구", "titleUrl": "https://www.google.com/search?q=%ED%8C%8C%EC%9D%B4%EC%8D%AC+%EB%A6%AC%EC%8A%A4%ED%8A%B8",
           "time": "2026-01-01T03:00:00Z", "locationInfos": [{"name": "somewhere"}]}
    df, _ = parse_records([rec], "브랜드 채널", "UCbrand")
    row = df.loc[0]
    assert row["text"] == "파이썬 리스트"
    assert row["profile"] == PERSONAL_PROFILE and row["profile_id"] is None
    assert not any("location" in c.lower() for c in df.columns)


def test_ads_removed():
    df, stats = parse_records([watch("Watched 광고", details=[{"name": "From Google Ads"}]), watch("Watched 영상")], "p")
    assert stats.ads_removed == 1 and len(df) == 1


def test_deleted_video_marked_without_channel():
    url_title = "Watched https://www.youtube.com/watch?v=gone"
    removed = {"header": "YouTube", "title": "Watched a video that has been removed", "time": "2026-01-01T03:00:00Z"}
    df, stats = parse_records([watch(url_title, vid="gone", channel=None), removed], "p")
    assert stats.deleted_videos == 2
    assert (df["text"] == DELETED_VIDEO).all() and df["channel"].isna().all()


def test_same_video_in_two_profiles_is_kept_but_exact_duplicates_removed():
    rec = watch("Watched 같은 영상")
    a = TakeoutExport("a.zip", {"x.json": [rec, dict(rec)]}, {"id": "UCa", "title": "채널 가"})
    b = TakeoutExport("b.zip", {"x.json": [dict(rec)]}, {"id": "UCb", "title": "채널 나"})
    result = build_events([a, b])
    assert result.duplicates_removed == 1
    assert sorted(result.events["profile"].astype(str)) == ["채널 가", "채널 나"]


def test_reupload_warns_and_does_not_double_count():
    a = TakeoutExport("a.zip", {"x.json": [watch("Watched 영상")]}, {"id": "UCa", "title": "채널 가"})
    a2 = TakeoutExport("a-again.zip", {"x.json": [watch("Watched 영상")]}, {"id": "UCa", "title": "채널 가"})
    result = build_events([a, a2])
    assert len(result.events) == 1 and len(result.warnings) == 1


def test_identify_profile_fallbacks():
    assert identify_profile(TakeoutExport("my-brand.zip")).method == "filename"
    unknown = identify_profile(TakeoutExport("takeout-20261022T061522Z-001.zip"), unknown_index=2)
    assert (unknown.label, unknown.method) == ("unknown-2", "unknown")


def test_user_label_overrides_identification():
    a = TakeoutExport("takeout-20261022T061522Z-001.zip", {"x.json": [watch("Watched 영상")]})
    result = build_events([a], labels={a.name: "취미 채널"})
    assert result.profiles[0].method == "user"
    assert result.events.loc[0, "profile"] == "취미 채널"


def test_load_single_json_and_skip_non_activity(tmp_path):
    path = tmp_path / "watch-history.json"
    path.write_text(json.dumps([watch("Watched 영상")], ensure_ascii=False), encoding="utf-8")
    export = load_takeout(path)
    assert export.record_count == 1

    other = tmp_path / "settings.json"
    other.write_text(json.dumps({"setting": True}), encoding="utf-8")
    assert load_takeout(other).skipped == [other.name]


# ---- Chrome 웹 방문 (PRD 4.4) ----

def chrome(url, time="2026-01-01T03:00:00.000Z", title="페이지 을(를) 방문했습니다."):
    rec = {"header": "Chrome", "title": title, "time": time, "products": ["Chrome"]}
    if url is not None:
        rec["titleUrl"] = f"https://www.google.com/url?q={quote_plus(url)}&usg=x"
    return rec


def test_web_domain_unwraps_and_keeps_only_host():
    wrapped = f"https://www.google.com/url?q={quote_plus('https://www.GitHub.com/me/repo?token=secret#x')}"
    assert web_domain(wrapped) == "github.com"
    assert web_domain("https://docs.python.org/3/") == "docs.python.org"


def test_web_domain_excludes_local_internal_and_duplicate_services():
    for url in ["http://localhost:8501/", "http://192.168.0.1/admin", "http://10.0.0.5/", "http://172.20.1.1/",
                "chrome://settings", "file:///C:/a.html", "https://www.google.com/search?q=x",
                "https://www.youtube.com/watch?v=abc", "https://www.youtube.com/results?search_query=x"]:
        assert web_domain(url) is None, url
    assert web_domain("https://www.youtube.com/@channel") == "youtube.com"
    assert web_domain("https://drive.google.com/drive") == "drive.google.com"


def test_chrome_record_is_web_visit_not_search_visited():
    assert classify(chrome("https://github.com/x")) == ("web_visit", "visited")
    assert classify(chrome(None, title="Chrome을 사용함")) is None


def test_chrome_records_parsed_with_domain_only():
    df, stats = parse_records([chrome("https://github.com/me/repo?token=secret"), chrome(None),
                               chrome("http://localhost:3000/")], "브랜드", "UCb")
    assert len(df) == 1 and stats.unsupported == 1 and stats.web_excluded == 1
    row = df.loc[0]
    assert (row["service"], row["text"], row["domain"], row["profile"]) == ("web_visit", "github.com", "github.com", PERSONAL_PROFILE)
    assert not df.astype(str).apply(lambda c: c.str.contains("secret|repo")).any().any()


def test_repeat_visits_within_one_minute_of_previous_visit_are_merged():
    # 직전 방문과 1분 안이면 묶는다: 03:00:00 → 03:00:40(묶음) → 03:01:30(직전과 50초, 묶음) → 03:03:00(90초, 새 방문)
    recs = [chrome("https://a.com/1", "2026-01-01T03:00:00Z"), chrome("https://a.com/2", "2026-01-01T03:00:40Z"),
            chrome("https://a.com/3", "2026-01-01T03:01:30Z"), chrome("https://a.com/4", "2026-01-01T03:03:00Z"),
            chrome("https://b.com/", "2026-01-01T03:00:10Z")]
    df, stats = parse_records(recs, "p")
    assert stats.web_repeats_merged == 2
    assert sorted(df["domain"]) == ["a.com", "a.com", "b.com"]


def test_user_excluded_domains_include_subdomains():
    recs = [chrome("https://mail.example.com/"), chrome("https://example.com/", "2026-01-01T04:00:00Z"),
            chrome("https://other.org/")]
    df, stats = parse_records(recs, "p", exclude_domains=["www.Example.com"])
    assert list(df["domain"]) == ["other.org"] and stats.web_blocked == 2


def test_search_visited_keeps_domain_only():
    rec = {"header": "Search", "title": "Visited https://site.com/private?x=1", "products": ["Search"],
           "titleUrl": f"https://www.google.com/url?q={quote_plus('https://site.com/private?x=1')}", "time": "2026-01-01T03:00:00Z"}
    df, _ = parse_records([rec], "p")
    assert (df.loc[0, "service"], df.loc[0, "activity"], df.loc[0, "text"]) == ("search", "visited", "site.com")


def test_browser_history_parsing():
    items = [
        {"url": "https://github.com/a", "title": "비밀 제목", "time_usec": 1767236400000000, "page_transition": "TYPED"},
        {"url": "https://github.com/a", "time_usec": 1767240000000000, "page_transition": "RELOAD"},
        {"url": "https://docs.python.org/", "time_usec": 1767243600000000, "page_transition": "LINK"},
    ]
    df, stats = parse_browser_history(items)
    assert stats.web_excluded == 1
    assert list(df["activity"]) == ["typed", "visited"]
    assert df.loc[0, "ts_kst"].hour == 12  # 2026-01-01 03:00 UTC → 12:00 KST
    assert "비밀 제목" not in df.astype(str).to_numpy()


def test_browser_history_preferred_over_my_activity_chrome(tmp_path):
    history = {"Browser History": [{"url": "https://github.com/a", "time_usec": 1767236400000000, "page_transition": "LINK"}]}
    path = tmp_path / "History.json"
    path.write_text(json.dumps(history), encoding="utf-8")
    bh = load_takeout(path)
    assert bh.record_count == 1 and bh.activity_files == {}
    my_activity = TakeoutExport("my.zip", {"c.json": [chrome("https://other.org/")]})
    result = build_events([my_activity, bh])
    assert list(result.events["domain"]) == ["github.com"]
    assert result.stats["my.zip"].chrome_skipped == 1
