"""POST /api/report

입력: /api/recommend 응답 전체({date, recommended_cities, errors}) 를 그대로 다시 보낸 것
출력: { "cities": [{city, summary, schedule:{morning, afternoon, evening}}], "markdown": "..." }

A1-2(travel_planner.py)의 리포트 생성(generate_report)에 대응한다. 클라이언트가 보낸
recommended_cities는 브라우저 localStorage 캐시를 거쳐올 수 있으므로 서버에서 다시
스키마를 검증한다(validate_report_request).
"""

from http.server import BaseHTTPRequestHandler

from _core import generate_report, get_openai_client, load_api_keys, validate_report_request
from _http import handle_errors, read_json_body, send_json

MAX_BODY_BYTES = 32 * 1024  # 지역별 맛집 목록까지 포함될 수 있어 32KB로 제한


def _handle(handler):
    body = read_json_body(handler, MAX_BODY_BYTES)
    travel_date, recommended_cities, errors = validate_report_request(body)

    openai_key, _ = load_api_keys()
    client = get_openai_client(openai_key)

    report = generate_report(client, travel_date.isoformat(), recommended_cities, errors)
    return report


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        handle_errors(self, lambda: _handle(self))

    def do_GET(self):
        send_json(self, 405, {"error": "POST 요청만 지원합니다."})
