"""Cody 프록시와 OpenAI 공식 API의 function calling(tools) 지원 여부 확인.

각 경로에서 2단계를 시험한다:
  1) tools 를 주고 질문 → 응답에 tool_calls 가 오는지 (모델이 도구를 고르는지)
  2) 도구 결과(role=tool)를 돌려줌 → 결과를 반영한 최종 답이 오는지
키 값은 출력하지 않는다. backend 폴더에서 실행: python scripts/probe_tools.py
"""
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.config import settings  # noqa: E402

TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_data_range",
        "description": "저장된 시계열 데이터에서 start_date~end_date 기간의 포인트를 조회한다.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["start_date", "end_date"],
        },
    },
}]
FAKE_RESULT = [{"date": "2026-03-02", "value": 171000, "memo": ""},
               {"date": "2026-03-03", "value": 174500, "memo": "전일 대비 +3.2% 급등"}]
MSGS = [{"role": "system", "content": "필요하면 도구를 호출해 데이터를 조회한 뒤 한국어로 짧게 답하세요."},
        {"role": "user", "content": "2026년 3월 2일부터 3월 3일까지 값을 알려줘"}]

PATHS = [
    ("cody", f"{settings.cody_base_url}/chat/completions", settings.cody_api_key, settings.cody_model),
    ("openai", "https://api.openai.com/v1/chat/completions", settings.openai_api_key, settings.openai_model),
]


def post(url, key, body, timeout):
    return httpx.post(url, headers={"Authorization": f"Bearer {key}"}, json=body, timeout=timeout)


for name, url, key, model in PATHS:
    print(f"\n=== {name} ({model}) ===")
    if not key:
        print("키 없음 — 건너뜀")
        continue
    t = time.time()
    try:
        r = post(url, key, {"model": model, "messages": MSGS, "tools": TOOLS, "tool_choice": "auto"}, 60)
    except httpx.HTTPError as e:
        print(f"1단계 요청 실패: {type(e).__name__}")
        continue
    print(f"1단계 HTTP {r.status_code} ({time.time() - t:.1f}s)")
    if r.status_code != 200:
        print("  오류 본문:", r.text[:300])
        continue
    msg = r.json()["choices"][0]["message"]
    calls = msg.get("tool_calls") or []
    print("  finish_reason:", r.json()["choices"][0].get("finish_reason"), "| tool_calls:", len(calls))
    for c in calls:
        print("   -", c["function"]["name"], c["function"]["arguments"])
    if not calls:
        print("  (도구를 고르지 않음) content:", (msg.get("content") or "")[:120])
        continue

    follow = MSGS + [msg] + [{"role": "tool", "tool_call_id": c["id"],
                              "content": json.dumps(FAKE_RESULT, ensure_ascii=False)} for c in calls]
    t = time.time()
    r2 = post(url, key, {"model": model, "messages": follow, "tools": TOOLS}, 60)
    print(f"2단계 HTTP {r2.status_code} ({time.time() - t:.1f}s)")
    if r2.status_code == 200:
        print("  최종 답:", (r2.json()["choices"][0]["message"].get("content") or "")[:150])
    else:
        print("  오류 본문:", r2.text[:300])
