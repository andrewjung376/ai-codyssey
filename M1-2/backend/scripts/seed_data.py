"""시드 데이터 준비 스크립트.

1) Yahoo Finance에서 삼성전자(005930.KS) 일별 종가를 받아 data/samsung_daily.csv 로 저장
     python scripts/seed_data.py fetch --range 1y
2) CSV를 Firestore `data` 컬렉션에 업로드 (이미 있는 날짜는 건너뜀 → 여러 번 실행해도 안전)
     python scripts/seed_data.py upload

backend 폴더에서 실행한다.
"""

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from services.seed import SEED_CSV, load_seed_items  # noqa: E402

SYMBOL = "005930.KS"
KST = dt.timezone(dt.timedelta(hours=9))
SURGE_PCT = 3.0  # 전일 대비 이 이상 움직인 날은 메모를 남긴다


def fetch(range_: str) -> list[dict]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}"
    res = httpx.get(url, params={"interval": "1d", "range": range_},
                    headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    res.raise_for_status()
    result = res.json()["chart"]["result"][0]
    closes = result["indicators"]["quote"][0]["close"]

    rows, prev = [], None
    for ts, close in zip(result["timestamp"], closes):
        if close is None:  # 휴장·미체결 구간
            continue
        close = round(close)
        memo = ""
        if prev:
            pct = (close - prev) / prev * 100
            if abs(pct) >= SURGE_PCT:
                memo = f"전일 대비 {pct:+.1f}% {'급등' if pct > 0 else '급락'}"
        rows.append({"date": dt.datetime.fromtimestamp(ts, KST).date().isoformat(), "value": close, "memo": memo})
        prev = close

    # 같은 날짜가 두 번 오는 경우(장중 갱신값) 마지막 값만 남긴다
    dedup = {r["date"]: r for r in rows}
    rows = sorted(dedup.values(), key=lambda r: r["date"])
    if rows:
        top = max(rows, key=lambda r: r["value"])
        low = min(rows, key=lambda r: r["value"])
        top["memo"] = " / ".join(filter(None, ["기간 최고가", top["memo"]]))
        low["memo"] = " / ".join(filter(None, ["기간 최저가", low["memo"]]))
    return rows


def write_csv(rows: list[dict]):
    SEED_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(SEED_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "value", "memo"])
        writer.writeheader()
        writer.writerows(rows)


def upload():
    from services.repository import FirestoreRepository
    from core.config import settings

    items = load_seed_items()
    if not items:
        sys.exit(f"{SEED_CSV} 가 없습니다. 먼저 fetch 를 실행하세요.")
    repo = FirestoreRepository(settings.firebase_service_account)
    existing = {d["date"] for d in repo.list_data()}
    new_items = [it for it in items if it["date"] not in existing]
    repo.bulk_insert_data(new_items)
    print(f"업로드 {len(new_items)}건 (기존 날짜 {len(items) - len(new_items)}건 건너뜀)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_fetch = sub.add_parser("fetch", help="Yahoo Finance → CSV")
    p_fetch.add_argument("--range", default="1y", help="Yahoo range 값 (예: 6mo, 1y, 2y)")
    sub.add_parser("upload", help="CSV → Firestore")
    args = parser.parse_args()

    if args.cmd == "fetch":
        rows = fetch(args.range)
        write_csv(rows)
        print(f"{len(rows)}건 저장: {SEED_CSV} ({rows[0]['date']} ~ {rows[-1]['date']})")
    else:
        upload()


if __name__ == "__main__":
    main()
