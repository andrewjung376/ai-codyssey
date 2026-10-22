"""합성 샘플 데이터로 전체 처리 흐름(로드 → 파싱 → 병합 → 집계)을 검증한다."""
import pandas as pd
import pytest

from src import make_sample
from src.features import (daily_counts, find_gaps, flag_outliers, moving_average, pct_change,
                          resample, weekday_hour_matrix)
from src.loader import load_takeout
from src.profiles import build_events, channel_overlap

PERSONAL, BRAND = "샘플 개인 채널", "샘플 요리 채널"


@pytest.fixture(scope="module")
def exports(tmp_path_factory):
    paths = make_sample.build(tmp_path_factory.mktemp("sample"))
    return [load_takeout(p) for p in paths]


@pytest.fixture(scope="module")
def result(exports):
    return build_events(exports)


def test_sample_is_reproducible(tmp_path, exports):
    again = [load_takeout(p) for p in make_sample.build(tmp_path)]
    assert [e.record_count for e in again] == [e.record_count for e in exports]


def test_loader_finds_files_in_english_and_korean_layouts(exports):
    personal, brand = exports
    assert len(personal.activity_files) == 4 and personal.skipped == []
    assert len(brand.activity_files) == 2 and brand.skipped == []
    assert personal.channel == {"id": "UCsamplePersonal0000001", "title": PERSONAL}
    assert brand.channel["title"] == BRAND  # 한국어 헤더 CSV


def test_profiles_identified_from_channel_csv(result):
    assert [(p.label, p.method) for p in result.profiles] == [(PERSONAL, "channel.csv"), (BRAND, "channel.csv")]
    assert set(result.events["profile"].astype(str)) == {"personal", PERSONAL, BRAND}


def test_cleaning_rules_applied(result):
    ev = result.events
    assert result.duplicates_removed > 0
    assert not ev.duplicated(subset=["profile", "service", "ts_kst", "text"]).any()
    assert not ev["text"].str.startswith("광고 영상").any()
    assert all(s.ads_removed > 0 and s.deleted_videos > 0 for s in result.stats.values())
    assert set(ev["service"].astype(str)) == {"search", "yt_watch", "yt_search"}
    assert (ev.loc[ev["service"] == "search", "profile"] == "personal").all()
    # 한국어 title도 문구가 떼어져 있어야 한다
    assert not ev["text"].str.contains("시청했습니다").any()


def test_daily_counts_cover_period_with_zero_filled(result):
    daily = daily_counts(result.events)
    assert len(daily) >= 100
    assert daily.index.min() == pd.Timestamp(make_sample.START)
    assert (daily.index.to_series().diff().dropna() == pd.Timedelta(days=1)).all()


def test_gap_detected_in_personal_profile(result):
    ev = result.events
    personal = ev[ev["profile"].isin(["personal", PERSONAL])]
    gaps = find_gaps(daily_counts(personal, by=None)["total"])
    assert len(gaps) == 1
    assert gaps.loc[0, "start"] == pd.Timestamp(make_sample.GAP_START)
    assert gaps.loc[0, "days"] == make_sample.GAP_DAYS


def test_binge_days_flagged_as_outliers(result):
    watch = daily_counts(result.events[result.events["profile"] == PERSONAL])["yt_watch"]
    flagged = set(watch.index[flag_outliers(watch)].date)
    assert make_sample.BINGE_DAYS <= flagged


def test_resample_and_rates(result):
    daily = daily_counts(result.events)
    weekly, monthly = resample(daily, "W"), resample(daily, "M")
    assert weekly.sum().equals(daily.sum()) and monthly.sum().equals(daily.sum())
    assert (weekly.index.weekday == 0).all() and (monthly.index.day == 1).all()
    ma = moving_average(daily["yt_watch"], 7)
    assert ma.iloc[:6].isna().all() and ma.iloc[6] == pytest.approx(daily["yt_watch"].iloc[:7].mean())
    assert not pct_change(weekly).isin([float("inf")]).any().any()


def test_weekday_hour_matrix(result):
    matrix = weekday_hour_matrix(result.events)
    assert matrix.shape == (7, 24) and matrix.to_numpy().sum() == len(result.events)
    assert list(matrix.index) == ["월", "화", "수", "목", "금", "토", "일"]


def test_channel_overlap_between_profiles(result):
    overlap = channel_overlap(result.events)
    personal_vs_brand = overlap[(overlap["profile_a"] != "personal") & (overlap["profile_b"] != "personal")]
    row = personal_vs_brand.iloc[0]
    assert row["common_channels"] == ["요리 채널 D", "음악 플레이리스트 E"]
    assert 0 < row["jaccard"] < 1
