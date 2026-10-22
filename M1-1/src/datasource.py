"""분석용 events 데이터를 준비한다.

mode
- "raw": data/raw의 실제 데이터만
- "sample": data/sample의 합성 데이터만
- "auto": 서비스별로 실제 데이터가 있으면 실제, 없으면 샘플 (기본값)
events에는 어느 쪽 데이터인지 알 수 있도록 `source`("raw"/"sample") 컬럼을 붙인다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .loader import TakeoutExport, load_takeout
from .parser import EVENT_COLUMNS
from .profiles import MergeResult, build_events

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
SAMPLE_DIR = ROOT / "data" / "sample"
SERVICES = ("search", "yt_watch", "yt_search", "web_visit")
_SUFFIXES = {".zip", ".json", ".csv"}


@dataclass
class Dataset:
    events: pd.DataFrame
    sources: dict[str, str]                      # 서비스 → "raw" / "sample" / "none"
    results: dict[str, MergeResult] = field(default_factory=dict)  # "raw" / "sample" → 병합 결과


def load_dir(directory: Path) -> list[TakeoutExport]:
    """폴더 안의 내보내기를 읽는다 (PRD 8.3).

    - zip 파일: 하나가 내보내기 하나
    - 하위 폴더(예: personal/, brand-요리/): 폴더 안의 파일 전체가 내보내기 하나
    - 폴더에 바로 놓인 json·csv 낱개 파일: 모두 묶어 내보내기 하나 (channel.csv가 같은 폴더의 기록과 연결되도록)
    """
    if not directory.exists():
        return []
    exports, loose = [], []
    for path in sorted(directory.iterdir()):
        if path.is_dir():
            files = sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in _SUFFIXES)
            if files:
                exports.append(_combine(path.name, files))
        elif path.suffix.lower() == ".zip":
            exports.append(load_takeout(path))
        elif path.suffix.lower() in _SUFFIXES:
            loose.append(path)
    if loose:
        exports.append(_combine(directory.name, loose))
    return exports


def _combine(name: str, paths: list[Path]) -> TakeoutExport:
    combined = TakeoutExport(name=name)
    for path in paths:
        part = load_takeout(path)
        for attr in ("activity_files", "browser_history"):
            getattr(combined, attr).update({f"{path.name}:{k}" if path.suffix == ".zip" else k: v
                                            for k, v in getattr(part, attr).items()})
        combined.channel = combined.channel or part.channel
        combined.skipped += part.skipped
    return combined


def load_dataset(mode: str = "auto", exclude_domains=(), raw_dir: Path = RAW_DIR,
                 sample_dir: Path = SAMPLE_DIR) -> Dataset:
    if mode not in ("raw", "sample", "auto"):
        raise ValueError(f"알 수 없는 mode: {mode}")
    results, frames = {}, []
    raw_services: set[str] = set()

    if mode in ("raw", "auto"):
        results["raw"] = build_events(load_dir(raw_dir), exclude_domains=exclude_domains)
        raw = results["raw"].events.assign(source="raw")
        raw_services = set(raw["service"].astype(str))
        frames.append(raw)
    if mode in ("sample", "auto"):
        results["sample"] = build_events(load_dir(sample_dir), exclude_domains=exclude_domains)
        sample = results["sample"].events.assign(source="sample")
        frames.append(sample[~sample["service"].astype(str).isin(raw_services)])

    frames = [f for f in frames if not f.empty]
    if frames:
        events = pd.concat([f.astype({c: "object" for c in ("profile", "service", "activity")}) for f in frames],
                           ignore_index=True)
    else:
        events = pd.DataFrame(columns=[*EVENT_COLUMNS, "source"])
    events = events.sort_values("ts_kst").reset_index(drop=True)
    for col in ("profile", "service", "activity", "source"):
        events[col] = events[col].astype("category")

    present = events.groupby("service", observed=True)["source"].first().astype(str).to_dict()
    sources = {s: present.get(s, "none") for s in SERVICES}
    return Dataset(events, sources, results)
