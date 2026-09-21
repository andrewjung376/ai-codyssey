"""
travel_planner.py의 두 에러 경로를 실제 API로 재현 검증하는 스크립트.
- 케이스 1: 맛집 검색 0건 (Kakao Local 실제 호출)
- 케이스 2: LLM JSON 파싱 실패 → 1회 재시도 (OpenAI 실제 호출)
프로덕션 코드(travel_planner.py)는 수정하지 않는다.
"""
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

import travel_planner as tp

load_dotenv()

openai_key = os.getenv("OPENAI_API_KEY")
kakao_key = os.getenv("KAKAO_REST_API_KEY")
client = OpenAI(api_key=openai_key)

print("=" * 60)
print("케이스 1: 맛집 검색 0건 (실제 Kakao Local API 호출)")
print("=" * 60)
errors_1 = []
# 실제로 존재할 수 없는 지명으로 검색해 0건을 유도한다.
nonsense_city = "존재하지않는가상의동네이름즤크르프"
restaurants = tp.search_restaurants(kakao_key, nonsense_city, errors_1)
print(f"검색어: '{nonsense_city} 맛집'")
print(f"결과 개수: {len(restaurants)}")
print(f"errors: {json.dumps(errors_1, ensure_ascii=False, indent=2)}")
assert restaurants == [], "맛집 리스트가 비어있지 않음 (0건 유도 실패)"
assert len(errors_1) == 1 and errors_1[0]["type"] == "EMPTY_RESULT", "EMPTY_RESULT 오류가 기록되지 않음"
print(">> PASS: 0건 발생 시 EMPTY_RESULT 기록, 프로그램 중단 없이 빈 리스트 반환 확인\n")


print("=" * 60)
print("케이스 2: LLM JSON 파싱 실패 → 최대 1회 재시도 (실제 OpenAI API 호출)")
print("=" * 60)
errors_2 = []

# request_recommendation과 동일한 재시도 로직을 그대로 사용하되,
# 1차 시도에서 의도적으로 필수 키가 없는 다른 스키마를 요청해 실패를 유도한다.
bad_prompt = (
    "아무 도시나 하나 골라서 JSON으로 출력해줘. "
    '반드시 이 키만 사용해: {"city": "", "temp": ""} '
    "recommended_cities 같은 키는 절대 쓰지 마."
)
messages = [{"role": "user", "content": bad_prompt}]

result = None

for attempt in range(2):
    response = client.chat.completions.create(
        model=tp.OPENAI_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    print(f"--- 시도 {attempt + 1} 원본 응답 ---")
    print(content)
    data = json.loads(content)

    try:
        tp.validate_recommendation(data)
    except ValueError as e:
        errors_2.append({
            "step": "recommendation",
            "type": "PARSE_ERROR",
            "message": f"스키마 검증 실패 (시도 {attempt + 1}/2): {e}",
        })
        print(f">> 스키마 검증 실패 감지: {e} (예상된 실패)")
        if attempt == 0:
            # 프로덕션 코드의 재시도 프롬프트를 그대로 사용
            messages = [{"role": "user", "content": tp.build_recommendation_prompt("2026-04-01", retry=True)}]
            continue
        result = None
        break
    else:
        result = data
        break

print(f"\n최종 errors: {json.dumps(errors_2, ensure_ascii=False, indent=2)}")
print(f"최종 result: {json.dumps(result, ensure_ascii=False, indent=2)}")

assert len(errors_2) == 1, f"PARSE_ERROR가 정확히 1회만 기록되어야 함 (실제: {len(errors_2)})"
assert result is not None, "재시도 후에도 유효한 스키마의 JSON을 받지 못함"
cities = result["recommended_cities"]
assert tp.MIN_CITIES <= len(cities) <= tp.MAX_CITIES, f"지역 개수가 범위를 벗어남: {len(cities)}"
print(">> PASS: 1차 시도 파싱/스키마 실패 → 재시도 프롬프트로 1회 재요청 → 지역 2~3곳 스키마 확보 확인")
