"""Vercel Python 함수(BaseHTTPRequestHandler)용 공용 HTTP 유틸리티.

recommend.py / report.py가 공통으로 쓰는 JSON 요청 파싱, 응답 전송, 예외 ->
HTTP 상태 코드 매핑을 모아둔다. "_" 접두사라 별도 엔드포인트로 노출되지 않는다.
"""

import json

from _core import ConfigError, UpstreamError, ValidationError


def read_json_body(handler, max_bytes):
    """요청 본문을 읽어 JSON으로 파싱한다. 크기 초과/파싱 실패 시 ValidationError."""
    length_header = handler.headers.get("Content-Length")
    try:
        content_length = int(length_header) if length_header else 0
    except ValueError:
        content_length = 0

    if content_length <= 0:
        raise ValidationError("요청 본문이 비어 있습니다.")
    if content_length > max_bytes:
        raise ValidationError(f"요청 본문이 너무 큽니다. (최대 {max_bytes}바이트)")

    raw = handler.rfile.read(content_length)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ValidationError(f"요청 본문이 올바른 JSON이 아닙니다: {e}")


def send_json(handler, status_code, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_errors(handler, func):
    """공통 예외 -> HTTP 상태 코드 매핑. 각 엔드포인트의 do_POST에서 호출한다."""
    try:
        result = func()
        send_json(handler, 200, result)
    except ValidationError as e:
        send_json(handler, 400, {"error": str(e)})
    except ConfigError as e:
        send_json(handler, 500, {"error": str(e)})
    except UpstreamError as e:
        send_json(handler, 502, {"error": "AI 응답을 받지 못했어요. 잠시 후 다시 시도해 주세요."})
        print(f"[upstream error] {e}")
    except Exception as e:
        send_json(handler, 500, {"error": "예상치 못한 오류가 발생했습니다."})
        print(f"[unhandled error] {type(e).__name__}: {e}")
