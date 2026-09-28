"""POST /api/recommend

입력: { "date": "YYYY-MM-DD", "preference": "선택, 200자 이내" }
출력: { "recommended_cities": [{city, weather, events, reason, restaurants}], "errors": [] }

A1-2(travel_planner.py)의 1차 추천(request_recommendation) + 맛집 검색
(search_restaurants_by_city)을 하나의 엔드포인트로 합친 것이다.
"""

from http.server import BaseHTTPRequestHandler

from _core import (
    UpstreamError,
    attach_restaurants,
    get_openai_client,
    load_api_keys,
    request_recommendation,
    validate_date_str,
    validate_preference,
)
from _http import handle_errors, read_json_body, send_json

MAX_BODY_BYTES = 2 * 1024  # 날짜 + 취향(최대 200자) 정도만 필요하므로 넉넉히 2KB로 제한


def _handle(handler):
    body = read_json_body(handler, MAX_BODY_BYTES)

    travel_date = validate_date_str(body.get("date"))
    preference = validate_preference(body.get("preference"))

    openai_key, kakao_key = load_api_keys()
    client = get_openai_client(openai_key)

    errors = []
    date_str = travel_date.isoformat()

    recommendation = request_recommendation(client, date_str, preference, errors)
    if recommendation is None:
        raise UpstreamError("1차 추천 생성에 실패했습니다.")

    recommendation = attach_restaurants(kakao_key, recommendation, errors)

    return {
        "recommended_cities": recommendation["recommended_cities"],
        "errors": errors,
    }


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        handle_errors(self, lambda: _handle(self))

    def do_GET(self):
        send_json(self, 405, {"error": "POST 요청만 지원합니다."})
