"""시드 데이터(CSV) 읽기. 메모리 저장소 초기화와 Firestore 업로드 스크립트가 함께 쓴다."""

import csv

from core.config import BACKEND_DIR

SEED_CSV = BACKEND_DIR / "data" / "samsung_daily.csv"


def load_seed_items(path=SEED_CSV) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return [
            {"date": row["date"], "value": float(row["value"]), "memo": row.get("memo", "")}
            for row in csv.DictReader(f)
        ]
