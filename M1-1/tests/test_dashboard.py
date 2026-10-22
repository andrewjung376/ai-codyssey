"""대시보드: 업로드 묶기, 보조 함수, Plotly 차트, Streamlit 앱 실행(AppTest) 테스트."""
import io
import json
import zipfile
from pathlib import Path
from urllib.parse import quote_plus

import pytest
from streamlit.testing.v1 import AppTest

from src import charts, make_sample
from src import features as F
from src.dashboard import add_labels, parse_phases
from src.datasource import build_dataset, group_uploads, load_dataset

APP = str(Path(__file__).resolve().parent.parent / "app.py")
WATCH = [{"header": "YouTube", "title": "영상 을(를) 시청했습니다.", "titleUrl": "https://www.youtube.com/watch?v=a",
          "subtitles": [{"name": "채널 가"}], "time": "2026-01-01T03:00:00Z"}]


@pytest.fixture(scope="module")
def sample_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("sample")
    make_sample.build(d)
    return d


@pytest.fixture(scope="module")
def raw_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("raw")
    visits = [{"header": "Chrome", "title": "x 을(를) 방문했습니다.", "products": ["Chrome"],
               "titleUrl": f"https://www.google.com/url?q={quote_plus(f'https://site{i % 4}.com/')}",
               "time": f"2026-{3 + i % 6:02d}-{1 + i % 28:02d}T0{i % 10}:00:00Z"} for i in range(400)]
    (d / "내활동.json").write_text(json.dumps(visits, ensure_ascii=False), encoding="utf-8")
    watch = [dict(WATCH[0], time=f"2026-{3 + i % 6:02d}-{1 + i % 28:02d}T1{i % 10}:00:00Z") for i in range(300)]
    (d / "시청 기록.json").write_text(json.dumps(watch, ensure_ascii=False), encoding="utf-8")
    return d


def test_group_uploads_keeps_zips_and_bundles_loose_files():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Takeout/YouTube/history/watch-history.json", json.dumps(WATCH))
    files = [("a.zip", buf.getvalue()), ("시청 기록.json", json.dumps(WATCH, ensure_ascii=False).encode()),
             ("채널.csv", "채널 ID,채널 제목(원본)\nUCme,내 채널\n".encode())]
    exports = group_uploads(files)
    assert [e.name for e in exports] == ["a.zip", "업로드 파일"]
    assert exports[1].channel["title"] == "내 채널" and exports[1].record_count == 1
    ds = build_dataset(exports, "upload")
    assert set(ds.events["source"]) == {"upload"} and ds.sources["yt_watch"] == "upload"


def test_parse_phases():
    phases, errors = parse_phases("AI 과정, 2026-07-01\n재직, 2025-01-01\n\n잘못된 줄\n이름 없음,\n, 2026-01-01")
    assert phases == [("재직", "2025-01-01"), ("AI 과정", "2026-07-01")]
    assert errors == ["잘못된 줄", "이름 없음,", ", 2026-01-01"]


def test_add_labels_masks_names(sample_dir):
    ev = load_dataset("sample", sample_dir=sample_dir).events
    shown = add_labels(ev, mask=False)
    watch = shown["service"] == "yt_watch"
    assert (shown.loc[watch, "label"].dropna() == shown.loc[watch, "channel"].dropna()).all()
    masked = add_labels(ev, mask=True)
    assert masked.loc[watch, "label"].dropna().str.match(r"^채널 \d+$").all()
    assert masked["profile"].astype(str).str.match(r"^프로필 \d+$").all()


def test_plotly_charts_render(sample_dir):
    ev = add_labels(load_dataset("sample", sample_dir=sample_dir).events, mask=False)
    daily = F.daily_by_service(ev)
    phases = [("전", "2025-01-01"), ("후", "2026-04-01")]
    figures = [
        charts.trend_chart(daily, 7, outliers={s: F.flag_outliers(x) for s, x in daily.items()}, phases=phases),
        charts.change_chart({s: F.resample(x, "W") for s, x in daily.items()}),
        charts.heatmap_chart(F.weekday_hour_matrix(ev), "히트맵"),
        charts.distribution_chart(ev),
        charts.top_n_chart(F.top_n(ev, "label", 5, "search"), "상위"),
        charts.track_chart(ev, ["파이썬", "없는키워드"], "W"),
        charts.profile_compare_chart(ev[ev["service"] == "yt_watch"]),
        charts.domain_trend_chart(ev[ev["service"] == "web_visit"], phases=phases),
        charts.combined_area_chart(daily, phases=phases),
        charts.phase_chart(daily, phases),
    ]
    for fig in figures:
        assert fig.data, fig.layout.title.text
        fig.to_json()  # 직렬화까지 오류가 없어야 브라우저에 그려진다


def _app(monkeypatch, sample_dir, raw_dir=None):
    monkeypatch.setenv("MYACTIVITY_SAMPLE_DIR", str(sample_dir))
    monkeypatch.setenv("MYACTIVITY_RAW_DIR", str(raw_dir or sample_dir / "no-raw"))
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    return at


def tab_labels(at):
    return [t.label for t in at.tabs]


def test_app_sample_mode_renders_all_tabs(monkeypatch, sample_dir):
    at = _app(monkeypatch, sample_dir)
    assert [r.options for r in at.radio][0] == ["샘플 데이터", "파일 업로드"]  # data/raw 없으면 메뉴 숨김
    assert tab_labels(at) == ["개요", "추세", "리듬", "관심사", "채널 비교", "웹 방문", "심화"]
    assert any("합성 샘플" in c.value for c in at.caption)


def test_app_filters_and_mask(monkeypatch, sample_dir):
    at = _app(monkeypatch, sample_dir)
    unit = next(r for r in at.radio if r.label == "집계 단위")
    unit.set_value("W").run()
    assert not at.exception
    at.toggle[0].set_value(True).run()
    assert not at.exception
    at.text_area[0].set_value("전, 2025-01-01\n후, 2026-04-01\n잘못됨").run()
    assert not at.exception
    assert "생활 단계" in tab_labels(at)
    assert any("잘못됨" in w.value for w in at.warning)


def test_app_raw_mode_prefills_phases(monkeypatch, sample_dir, raw_dir):
    at = _app(monkeypatch, sample_dir, raw_dir)
    source = at.radio[0]
    assert source.options == ["샘플 데이터", "파일 업로드", "로컬 data/raw"]
    source.set_value("raw").run()
    assert not at.exception
    assert "생활 단계" in tab_labels(at) and "웹 방문" in tab_labels(at)
    assert not any("합성 샘플" in c.value for c in at.caption)
