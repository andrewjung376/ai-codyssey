"""datasource·privacy 동작과 viz 그래프 스모크 테스트."""
import json
from urllib.parse import quote_plus

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pytest  # noqa: E402

from src import features as F  # noqa: E402
from src import make_sample, privacy, viz  # noqa: E402
from src.datasource import load_dataset  # noqa: E402


@pytest.fixture(scope="module")
def dirs(tmp_path_factory):
    sample = tmp_path_factory.mktemp("sample")
    make_sample.build(sample)
    raw = tmp_path_factory.mktemp("raw")
    visits = [{"header": "Chrome", "title": "x 을(를) 방문했습니다.", "products": ["Chrome"],
               "titleUrl": f"https://www.google.com/url?q={quote_plus(f'https://site{i % 3}.com/p')}",
               "time": f"2026-01-{1 + i % 28:02d}T0{i % 10}:00:00Z"} for i in range(60)]
    (raw / "내활동.json").write_text(json.dumps(visits, ensure_ascii=False), encoding="utf-8")
    return raw, sample


def test_auto_mode_uses_raw_per_service_and_fills_rest_with_sample(dirs):
    raw, sample = dirs
    ds = load_dataset("auto", raw_dir=raw, sample_dir=sample)
    assert ds.sources == {"search": "sample", "yt_watch": "sample", "yt_search": "sample", "web_visit": "raw"}
    web = ds.events[ds.events["service"] == "web_visit"]
    assert (web["source"] == "raw").all() and set(web["domain"]) == {"site0.com", "site1.com", "site2.com"}


def test_raw_and_sample_modes(dirs, tmp_path):
    raw, sample = dirs
    assert set(load_dataset("raw", raw_dir=raw, sample_dir=sample).events["source"]) == {"raw"}
    assert set(load_dataset("sample", raw_dir=raw, sample_dir=sample).events["source"]) == {"sample"}
    empty = load_dataset("raw", raw_dir=tmp_path / "none", sample_dir=sample)
    assert empty.events.empty and set(empty.sources.values()) == {"none"}


def test_privacy_review_and_masking(tmp_path):
    import pandas as pd
    values = pd.Series(["a.com", "b.com", "a.com", "c.com", "a.com", "b.com"])
    path = privacy.write_review(values, tmp_path / "review.md")
    assert privacy.read_public_names(path) is None  # 아직 아무것도 체크하지 않음
    assert list(privacy.mask_labels(values, None)) == ["도메인 1", "도메인 2", "도메인 1", "도메인 3", "도메인 1", "도메인 2"]

    path.write_text(path.read_text(encoding="utf-8").replace("- [ ] `b.com`", "- [x] `b.com`"), encoding="utf-8")
    public = privacy.read_public_names(path)
    assert public == {"b.com"}
    assert set(privacy.mask_labels(values, public)) == {"b.com", "기타 도메인"}
    privacy.write_review(values, path)  # 다시 써도 체크가 유지된다
    assert privacy.read_public_names(path) == {"b.com"}


def test_all_report_figures_render(dirs, tmp_path):
    raw, sample = dirs
    viz.setup_style()
    ds = load_dataset("auto", raw_dir=raw, sample_dir=sample)
    ev = ds.events.assign(label=ds.events["text"])
    series = F.daily_by_service(ev)
    assert all(x.index.is_monotonic_increasing for x in series.values())
    figures = {
        "01": viz.plot_daily_trend(series, ds.sources),
        "02": viz.plot_weekly_change({s: F.pct_change(F.resample(x, "W")) for s, x in series.items()}, ds.sources),
        "03": viz.plot_heatmaps({str(s): F.weekday_hour_matrix(g) for s, g in ev.groupby("service", observed=True)}),
        "04": viz.plot_outliers_gaps(series, {s: F.flag_outliers(x) for s, x in series.items()},
                                     {s: F.find_gaps(x) for s, x in series.items()}, ds.sources),
        "05": viz.plot_top_by_quarter([("검색어", ev[ev["service"] == "search"], "label"),
                                       ("채널", ev[ev["service"] == "yt_watch"], "channel")]),
        "06": viz.plot_profile_compare(ev[ev["service"] == "yt_watch"]),
        "07": viz.plot_domain_trend(ev[ev["service"] == "web_visit"]),
        "08": viz.plot_combined_activity(series, ds.sources),
    }
    for name, fig in figures.items():
        assert fig.axes, name
        assert viz.save(fig, f"{name}.png", tmp_path).stat().st_size > 0
        plt.close(fig)
    assert viz.service_label("search", ds.sources) == "Google 검색 (샘플)"
    assert viz.service_label("web_visit", ds.sources) == "웹 방문"


def test_load_dir_combines_loose_files_and_subfolders(tmp_path):
    from src.datasource import load_dir
    watch = [{"header": "YouTube", "title": "영상 을(를) 시청했습니다.", "titleUrl": "https://www.youtube.com/watch?v=a",
              "subtitles": [{"name": "채널"}], "time": "2026-01-01T03:00:00Z"}]
    (tmp_path / "시청 기록.json").write_text(json.dumps(watch, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "채널.csv").write_text("채널 ID,채널 제목(원본)\nUCme,내 채널\n", encoding="utf-8")
    brand = tmp_path / "brand-요리"
    brand.mkdir()
    (brand / "watch-history.json").write_text(json.dumps(watch, ensure_ascii=False), encoding="utf-8")
    exports = load_dir(tmp_path)
    assert [e.name for e in exports] == ["brand-요리", tmp_path.name]
    loose = exports[1]
    assert loose.channel == {"id": "UCme", "title": "내 채널"} and loose.record_count == 1


def test_outliers_on_sparse_series_use_active_days_only():
    import pandas as pd
    sparse = pd.Series([0] * 50 + [1, 1, 2, 1, 1, 9])
    flagged = F.flag_outliers(sparse)
    assert flagged.sum() == 1 and flagged.iloc[-1]
    assert not F.flag_outliers(pd.Series([0, 0, 0])).any()


PHASES = [("재직", "2025-01-01"), ("퇴사 후", "2026-04-01"), ("AI 교육", "2026-04-27"), ("AI 과정", "2026-07-01")]


def test_assign_phase_and_summary():
    import pandas as pd
    dates = pd.DatetimeIndex(["2025-12-31", "2026-04-01", "2026-04-26", "2026-04-27", "2026-10-01"])
    assert list(F.assign_phase(dates, PHASES)) == ["재직", "퇴사 후", "퇴사 후", "AI 교육", "AI 과정"]
    aware = pd.Series(pd.to_datetime(["2026-03-31T23:30:00+09:00", "2026-04-01T00:10:00+09:00"]))
    assert list(F.assign_phase(aware, PHASES)) == ["재직", "퇴사 후"]  # KST 날짜 기준

    idx = pd.date_range("2026-03-25", "2026-07-05", freq="D")
    series = pd.Series(1, index=idx)
    events = pd.DataFrame({"ts_kst": (idx + pd.Timedelta(hours=14)).tz_localize("Asia/Seoul")})
    table = F.phase_summary(events, series, PHASES)
    assert list(table.index) == ["재직", "퇴사 후", "AI 교육", "AI 과정"]
    assert table.loc["퇴사 후", "일수"] == 26 and table.loc["AI 과정", "피크 시간"] == 14
    assert table.drop(columns="기간").dtypes.eq(float).all()  # round(1)이 적용되려면 숫자 타입이어야 한다


def test_phase_figures_render(dirs, tmp_path):
    raw, sample = dirs
    ds = load_dataset("sample", raw_dir=raw, sample_dir=sample)
    series = F.daily_by_service(ds.events)
    for fig in (viz.plot_phase_compare(ds.events, series, PHASES, ds.sources),
                viz.plot_daily_trend(series, ds.sources, phases=PHASES),
                viz.plot_combined_activity(series, ds.sources, phases=PHASES)):
        assert viz.save(fig, "p.png", tmp_path).stat().st_size > 0
        plt.close(fig)
