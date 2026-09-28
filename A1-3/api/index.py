"""POST /api

단일 Vercel Python 엔트리포인트. 요청 본문의 "action" 값으로 내부에서
recommend/report 두 흐름으로 라우팅한다.

- action: "recommend" -> { date, preference } -> api._core.handle_recommend()
- action: "report"    -> { date, recommended_cities, errors } -> api._core.handle_report()

## 파일을 하나로 합친 이유
Vercel Python 런타임은 프로젝트를 "하나의 애플리케이션"으로 빌드하며, 진입점은
app/index/server/main/wsgi/asgi 라는 이름의 파일에서만 자동으로 인식한다
("", src/, app/, api/ 아래). 이전에는 api/recommend.py와 api/report.py가 각각
`handler`를 내보내는 별도 파일이었는데, Vercel이 "둘 중 어느 게 진짜 진입점인지
알 수 없다"며 빌드에 실패했다. 그래서 인식 가능한 이름(index)의 파일 하나만
두고, 실제 라우팅은 요청 본문의 action 필드로 이 파일 안에서 처리한다.

실제 비즈니스 로직(검증, OpenAI/Kakao 호출)은 api/_core.py에 그대로 있고,
이 파일은 HTTP 요청을 읽고 응답을 쓰는 얇은 어댑터 역할만 한다.
"""

from http.server import BaseHTTPRequestHandler

from _core import ValidationError, handle_recommend, handle_report
from _http import handle_errors, read_json_body, send_json

MAX_BODY_BYTES = 32 * 1024  # 지역별 맛집 목록까지 포함될 수 있어 32KB로 제한


def _handle(handler):
    body = read_json_body(handler, MAX_BODY_BYTES)
    action = body.get("action")

    if action == "recommend":
        return handle_recommend(body)
    if action == "report":
        return handle_report(body)

    raise ValidationError('action 값은 "recommend" 또는 "report"여야 합니다.')


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        handle_errors(self, lambda: _handle(self))

    def do_GET(self):
        send_json(self, 405, {"error": "POST 요청만 지원합니다."})
