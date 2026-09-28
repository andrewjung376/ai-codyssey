"""AI여행추천(AI TripPick) 공용 로직.

A1-2(`travel_planner.py`)의 CLI 파이프라인(1차 추천 -> 맛집 검색 -> 리포트 생성)을
웹 서비스용으로 이식한 모듈이다. 파일명이 "_"로 시작하므로 Vercel이 별도의
API 엔드포인트로 노출하지 않고, api/index.py가 이 모듈을 가져다 쓴다.

- 모든 텍스트 응답은 한글로만 작성하도록 프롬프트에서 강제한다 (A1-2와 동일 정책).
- 클라이언트(브라우저)가 보낸 값은 그대로 신뢰하지 않고 서버에서 다시 검증한다.
"""

import json
import os
import re
from datetime import date, datetime

from dotenv import load_dotenv
from openai import OpenAI
import requests

# Vercel(vercel dev/배포)은 환경 변수를 자동으로 주입하므로 보통은 불필요하지만,
# 로컬에서 이 모듈을 직접 테스트할 때를 위해 .env가 있으면 읽어들인다.
# .env가 없으면 아무 동작도 하지 않으므로 배포 환경에 영향이 없다.
load_dotenv()

# 1순위: Codyssey 과정에서 제공하는 OpenAI 호환 프록시. openai SDK 대신
# requests로 직접 호출한다(제공된 예제와 동일한 방식).
# 2순위(폴백): 프록시 호출이 실패하면 OPENAI_API_KEY + openai SDK로 재시도한다.
CODY_CHAT_COMPLETIONS_URL = "https://copa.codyssey.kr/v1/chat/completions"
CODY_MODEL = "gpt-5-mini"
OPENAI_FALLBACK_MODEL = "gpt-4o-mini"
# Vercel 함수 maxDuration(30초) 안에 "Cody 시도 + (실패 시) OpenAI 폴백"이 모두 끝나야 하므로
# Cody 쪽 타임아웃을 짧게 잡아, 느릴 때 폴백에 쓸 시간을 남겨둔다.
CODY_TIMEOUT_SECONDS = 28  # 실측 응답 시간(약 26초)보다 약간 여유를 둔 값
# 최악의 경우(Cody 타임아웃 28초 + 재시도 시 OpenAI 2회)도 Vercel maxDuration(60초)
# 안에 들어오도록 15초로 잡는다: 28 + 15 + 15 = 58초.
OPENAI_TIMEOUT_SECONDS = 15

KEY_SOURCE_CODY = "cody"
KEY_SOURCE_OPENAI = "openai"

KAKAO_KEYWORD_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
RESTAURANT_COUNT = 5

MIN_CITIES = 2
MAX_CITIES = 3
NO_DATA_TEXT = "데이터 없음"
RAW_RESPONSE_PREVIEW_LEN = 200

MAX_PREFERENCE_LEN = 200
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ValidationError(Exception):
    """사용자 입력 오류. 호출부에서 HTTP 400으로 변환한다."""


class UpstreamError(Exception):
    """OpenAI/Kakao 등 외부 서비스 호출이 최종적으로 실패한 경우. HTTP 502로 변환한다."""


class ConfigError(Exception):
    """서버 환경 변수(API 키) 미설정. HTTP 500으로 변환한다."""


# ---------------------------------------------------------------------------
# 입력 검증
# ---------------------------------------------------------------------------

def validate_date_str(date_str):
    """'YYYY-MM-DD' 형식과 오늘 이후 날짜인지 검증하고 date 객체를 반환한다."""
    if not date_str or not isinstance(date_str, str):
        raise ValidationError("여행 날짜를 입력해 주세요.")

    if not DATE_PATTERN.match(date_str):
        raise ValidationError('날짜 형식이 올바르지 않습니다. "YYYY-MM-DD" 형식으로 입력해 주세요. (예: 2026-03-15)')

    try:
        parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise ValidationError('날짜 형식이 올바르지 않습니다. "YYYY-MM-DD" 형식으로 입력해 주세요. (예: 2026-03-15)')

    if parsed < date.today():
        raise ValidationError("여행 날짜는 오늘 이후로 선택해 주세요.")

    return parsed


def validate_preference(preference):
    """선택 입력값(여행 취향)을 검증한다. 없으면 None을 반환한다."""
    if preference is None or preference == "":
        return None
    if not isinstance(preference, str):
        raise ValidationError("여행 취향 값이 올바르지 않습니다.")
    if len(preference) > MAX_PREFERENCE_LEN:
        raise ValidationError(f"여행 취향은 {MAX_PREFERENCE_LEN}자 이내로 입력해 주세요.")
    return preference


# ---------------------------------------------------------------------------
# 환경 변수 / 클라이언트
# ---------------------------------------------------------------------------

def load_api_keys():
    cody_key = os.environ.get("CODY_OPENAI_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    kakao_key = os.environ.get("KAKAO_REST_API_KEY")

    missing = []
    if not cody_key and not openai_key:
        missing.append("CODY_OPENAI_API_KEY 또는 OPENAI_API_KEY")
    if not kakao_key:
        missing.append("KAKAO_REST_API_KEY")

    if missing:
        # 키 값은 절대 로그/응답에 남기지 않고, 누락된 키 "이름"만 서버 로그에 남긴다.
        print(f"[config error] 다음 환경변수가 설정되지 않았습니다: {', '.join(missing)}")
        raise ConfigError("서비스 설정 오류입니다.")

    return cody_key, openai_key, kakao_key


def call_cody_proxy(api_key, messages, json_mode=False):
    """Codyssey OpenAI 호환 프록시(copa.codyssey.kr)에 채팅 완성 요청을 보낸다.

    openai SDK를 쓰지 않고 requests로 직접 호출한다 (제공된 예제와 동일한 방식).
    성공 시 첫 번째 choice의 메시지 content(string)를 반환한다.

    주의: 이 프록시는 response_format={"type":"json_object"}를 지원하지 않는다
    (400 "Requested feature is not supported"). 그래서 json_mode는 여기서
    쓰지 않고, JSON 전용 출력은 프롬프트 지시문(build_*_prompt)에만 의존한다.
    openai SDK 폴백 경로(call_openai_sdk)에서는 정상 지원되므로 그대로 쓴다.
    """
    payload = {"model": CODY_MODEL, "messages": messages}

    response = requests.post(
        CODY_CHAT_COMPLETIONS_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=CODY_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def call_openai_sdk(api_key, messages, json_mode=False):
    """폴백 경로: OPENAI_API_KEY + openai SDK로 채팅 완성 요청을 보낸다."""
    client = OpenAI(api_key=api_key, timeout=OPENAI_TIMEOUT_SECONDS)
    kwargs = {"model": OPENAI_FALLBACK_MODEL, "messages": messages}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def call_llm(cody_key, openai_key, messages, json_mode=False, try_cody=True):
    """1순위 Codyssey 프록시(CODY_OPENAI_API_KEY) -> 실패 시 2순위 OpenAI SDK(OPENAI_API_KEY).

    성공하면 (응답 content, 사용된 키 소스: KEY_SOURCE_CODY|KEY_SOURCE_OPENAI)를 반환한다.
    둘 다 실패하면 마지막 예외를 그대로 올린다.

    try_cody=False면 Cody 시도를 건너뛰고 바로 OpenAI로 간다. Cody는 느릴 때
    CODY_TIMEOUT_SECONDS(28초)까지 걸릴 수 있어서, 같은 요청 안에서 재시도할 때
    Cody를 또 시도하면 Vercel 함수 제한(60초)을 넘길 위험이 크다. 그래서
    request_recommendation()/generate_report()의 재시도(2번째 시도)에서는
    try_cody=False로 호출해 시간 예산을 지킨다.
    """
    cody_error = None
    if cody_key and try_cody:
        try:
            content = call_cody_proxy(cody_key, messages, json_mode=json_mode)
            return content, KEY_SOURCE_CODY
        except Exception as e:
            cody_error = e
            print(f"[cody proxy failed, falling back to OPENAI_API_KEY] {e}")

    if not openai_key:
        raise cody_error if cody_error else ConfigError("서비스 설정 오류입니다.")

    content = call_openai_sdk(openai_key, messages, json_mode=json_mode)
    return content, KEY_SOURCE_OPENAI


# ---------------------------------------------------------------------------
# [1/2] 1차 추천 (recommend)
# ---------------------------------------------------------------------------

def build_recommendation_prompt(travel_date, preference=None, retry=False):
    schema_hint = (
        '{"recommended_cities": ['
        '{"city": "", "weather": "", "events": [], "reason": ""}, '
        '{"city": "", "weather": "", "events": [], "reason": ""}'
        ']}'
    )
    preference_line = f"\n사용자 취향: {preference}" if preference else ""

    if retry:
        return (
            f"{travel_date}에 여행하기 좋은 국내 지역을 서로 다른 {MIN_CITIES}~{MAX_CITIES}곳 추천해줘."
            f"{preference_line}\n"
            "반드시 아래 형태의 JSON 객체 하나만 출력해. recommended_cities는 배열이고, "
            "배열의 각 항목은 city, weather, events, reason 4개 키만 가져야 해. "
            "다른 설명, 마크다운, 코드블록 없이 순수 JSON만 출력해.\n"
            f"{schema_hint}"
        )
    return (
        f"{travel_date}에 여행하기 좋은 국내 지역을 서로 다른 {MIN_CITIES}~{MAX_CITIES}곳 추천해줘."
        f"{preference_line}\n"
        "아래 JSON 스키마를 반드시 지켜서 출력해.\n"
        f"- recommended_cities: array ({MIN_CITIES}~{MAX_CITIES}개), 각 항목은 아래 4개 키를 가진 객체\n"
        "  - city: string (예: \"제주\", \"강릉\")\n"
        "  - weather: string (해당 시기 그 지역의 일반적 날씨 요약)\n"
        "  - events: array of string (그 지역의 행사/축제 후보 1~3개)\n"
        "  - reason: string (그 지역을 추천하는 근거 2~4문장)\n"
        "실제 정확한 예보/행사 데이터가 없다면 그 시기의 일반적인 경향으로 서술해.\n"
        "모든 텍스트 값은 한글로만 작성해. 한자, 일본어 등 다른 문자를 섞지 마."
    )


def validate_recommendation(data):
    if not isinstance(data, dict) or "recommended_cities" not in data:
        raise ValueError("필수 키 누락: {'recommended_cities'}")

    cities = data["recommended_cities"]
    if not isinstance(cities, list) or not (MIN_CITIES <= len(cities) <= MAX_CITIES):
        raise ValueError(
            f"recommended_cities는 {MIN_CITIES}~{MAX_CITIES}개의 배열이어야 함 (실제: {cities})"
        )

    required_sub_keys = {"city", "weather", "events", "reason"}
    for city_info in cities:
        if not isinstance(city_info, dict) or not required_sub_keys.issubset(city_info.keys()):
            missing = required_sub_keys - (city_info.keys() if isinstance(city_info, dict) else set())
            raise ValueError(f"recommended_cities 항목의 필수 키 누락: {missing}")

        for key in ("city", "weather", "reason"):
            if not isinstance(city_info[key], str):
                raise ValueError(f"'{key}'는 string이어야 함 (실제 타입: {type(city_info[key]).__name__})")

        events = city_info["events"]
        if not isinstance(events, list) or not all(isinstance(e, str) for e in events):
            raise ValueError(f"'events'는 string 배열이어야 함 (실제: {events})")


def request_recommendation(cody_key, openai_key, travel_date, preference, errors):
    """1차 추천을 생성한다. 성공하면 (data, key_source)를, 최종 실패하면 (None, None)을 반환한다."""
    messages = [{"role": "user", "content": build_recommendation_prompt(travel_date, preference)}]

    for attempt in range(2):
        content = None
        try:
            content, key_source = call_llm(
                cody_key, openai_key, messages, json_mode=True, try_cody=(attempt == 0)
            )
            data = json.loads(content)
            validate_recommendation(data)
            return data, key_source
        except (json.JSONDecodeError, ValueError) as e:
            preview = None
            if content:
                preview = content[:RAW_RESPONSE_PREVIEW_LEN]
                if len(content) > RAW_RESPONSE_PREVIEW_LEN:
                    preview += "..."
            errors.append({
                "step": "recommendation",
                "type": "PARSE_ERROR",
                "message": f"JSON 파싱 실패 (시도 {attempt + 1}/2): {e}",
                "raw_response_preview": preview,
            })
            if attempt == 0:
                messages = [{
                    "role": "user",
                    "content": build_recommendation_prompt(travel_date, preference, retry=True),
                }]
                continue
            return None, None
        except Exception as e:
            errors.append({
                "step": "recommendation",
                "type": "API_ERROR",
                "message": f"AI 호출 실패: {e}",
            })
            return None, None

    return None, None


# ---------------------------------------------------------------------------
# 맛집 검색 (Kakao Local)
# ---------------------------------------------------------------------------

def search_restaurants(kakao_key, city, errors):
    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    params = {"query": f"{city} 맛집", "size": RESTAURANT_COUNT}

    try:
        response = requests.get(KAKAO_KEYWORD_SEARCH_URL, headers=headers, params=params, timeout=10)

        if response.status_code in (401, 403):
            errors.append({
                "step": "place_search",
                "city": city,
                "type": "AUTH_ERROR",
                "message": f"HTTP {response.status_code}: {response.text}",
            })
            return []

        response.raise_for_status()
        documents = response.json().get("documents", [])

        if not documents:
            errors.append({
                "step": "place_search",
                "city": city,
                "type": "EMPTY_RESULT",
                "message": f"0 results for query={city} 맛집",
            })
            return []

        restaurants = []
        for doc in documents[:RESTAURANT_COUNT]:
            restaurants.append({
                "name": doc.get("place_name", ""),
                "address": doc.get("road_address_name") or doc.get("address_name", ""),
                "category": doc.get("category_name", ""),
                "url": doc.get("place_url", ""),
            })
        return restaurants

    except requests.exceptions.RequestException as e:
        errors.append({
            "step": "place_search",
            "city": city,
            "type": "NETWORK_ERROR",
            "message": str(e),
        })
        return []


def attach_restaurants(kakao_key, recommendation, errors):
    """recommended_cities의 각 지역 객체에 'restaurants' 키를 추가해 반환한다."""
    for city_info in recommendation["recommended_cities"]:
        city = city_info["city"]
        restaurants = search_restaurants(kakao_key, city, errors)
        city_info["restaurants"] = restaurants
    return recommendation


# ---------------------------------------------------------------------------
# [2/2] 리포트 생성 (report)
# ---------------------------------------------------------------------------

def validate_report_request(payload):
    """/api/report로 들어온 클라이언트 제공 데이터를 서버에서 다시 검증한다."""
    if not isinstance(payload, dict):
        raise ValidationError("요청 형식이 올바르지 않습니다.")

    travel_date = validate_date_str(payload.get("date"))

    recommended_cities = payload.get("recommended_cities")
    try:
        validate_recommendation({"recommended_cities": recommended_cities})
    except ValueError as e:
        raise ValidationError(f"추천 데이터 형식이 올바르지 않습니다: {e}")

    errors = payload.get("errors")
    if errors is None:
        errors = []
    if not isinstance(errors, list):
        raise ValidationError("errors 형식이 올바르지 않습니다.")

    return travel_date, recommended_cities, errors


def build_report_prompt(travel_date, recommended_cities, errors):
    cities_text = json.dumps({"recommended_cities": recommended_cities}, ensure_ascii=False, indent=2)
    schema_hint = (
        '{"cities": ['
        '{"city": "", "summary": "", "schedule": {"morning": "", "afternoon": "", "evening": ""}}'
        '], "markdown": ""}'
    )

    return (
        f"아래 정보를 바탕으로 {travel_date} 국내 여행 추천 리포트를 작성해줘.\n"
        f"추천 지역은 총 {len(recommended_cities)}곳이며, 지역마다 요약과 1일 일정을 만들어야 해.\n\n"
        f"[지역별 추천 정보 + 맛집]\n{cities_text}\n\n"
        f"[처리 중 발생한 오류 목록] (없으면 빈 배열)\n{json.dumps(errors, ensure_ascii=False)}\n\n"
        "반드시 아래 JSON 스키마 하나만 출력해 (다른 설명, 마크다운 코드블록 없이 순수 JSON만):\n"
        f"{schema_hint}\n\n"
        "- cities: recommended_cities와 같은 순서, 같은 지역 수만큼 생성\n"
        "  - summary: 그 지역 추천 이유와 맛집을 반영한 2~3문장 요약\n"
        "  - schedule.morning/afternoon/evening: 각 1~2문장의 간단한 일정 제안. "
        f"맛집 데이터가 없으면 일정에서 식사 추천은 생략하고 \"{NO_DATA_TEXT}\"라는 표현을 자연스럽게 포함해\n"
        "- markdown: 위 cities 내용을 사람이 읽기 좋은 Markdown 리포트 전체로 작성 "
        f"(# {travel_date} 국내 여행 추천 리포트 로 시작, 지역마다 ### 소제목, "
        "마지막에 '## 오류 요약' 섹션으로 errors를 요약. errors가 비어 있으면 '오류 없음'이라고 표기)\n"
        "모든 텍스트는 한글로만 작성해 (한자, 일본어 등 다른 문자를 섞지 마)."
    )


def validate_report_response(data, expected_city_count):
    if not isinstance(data, dict):
        raise ValueError("응답이 JSON 객체가 아님")

    cities = data.get("cities")
    if not isinstance(cities, list) or len(cities) != expected_city_count:
        raise ValueError(f"cities는 {expected_city_count}개의 배열이어야 함")

    for city_info in cities:
        if not isinstance(city_info, dict):
            raise ValueError("cities 항목이 객체가 아님")
        for key in ("city", "summary"):
            if not isinstance(city_info.get(key), str):
                raise ValueError(f"'{key}'는 string이어야 함")
        schedule = city_info.get("schedule")
        if not isinstance(schedule, dict):
            raise ValueError("schedule이 객체가 아님")
        for key in ("morning", "afternoon", "evening"):
            if not isinstance(schedule.get(key), str):
                raise ValueError(f"schedule.{key}는 string이어야 함")

    if not isinstance(data.get("markdown"), str):
        raise ValueError("markdown은 string이어야 함")


def generate_report(cody_key, openai_key, travel_date, recommended_cities, errors):
    """리포트를 생성한다. 성공하면 (data, key_source)를 반환한다.

    request_recommendation()과 마찬가지로, 스키마 검증 실패(예: cities 개수 불일치) 시
    한 번 더 같은 프롬프트로 재시도한다. LLM이 배열 길이 지시를 가끔 놓치는 것을 완화하기 위함이다.
    """
    prompt = build_report_prompt(travel_date, recommended_cities, errors)
    messages = [{"role": "user", "content": prompt}]
    expected_count = len(recommended_cities)
    last_error = None

    for attempt in range(2):
        content = None
        try:
            content, key_source = call_llm(
                cody_key, openai_key, messages, json_mode=True, try_cody=(attempt == 0)
            )
            data = json.loads(content)
            validate_report_response(data, expected_count)
            return data, key_source
        except (json.JSONDecodeError, ValueError) as e:
            preview = content[:RAW_RESPONSE_PREVIEW_LEN] if content else None
            last_error = f"{e} (raw preview: {preview})" if preview else str(e)
            if attempt == 0:
                messages = [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": content or ""},
                    {
                        "role": "user",
                        "content": (
                            f"방금 응답이 스키마를 어겼어({e}). "
                            f"cities는 정확히 {expected_count}개여야 하고, 각 항목은 city/summary/schedule"
                            "(morning/afternoon/evening)를 모두 가져야 해. markdown도 포함해서 "
                            "같은 JSON 스키마로 다시 전체를 출력해."
                        ),
                    },
                ]
                continue
            raise UpstreamError(f"리포트 응답 형식이 올바르지 않습니다: {last_error}") from e
        except UpstreamError:
            raise
        except Exception as e:
            raise UpstreamError(f"AI 호출 실패: {e}") from e

    raise UpstreamError(f"리포트 응답 형식이 올바르지 않습니다: {last_error}")


# ---------------------------------------------------------------------------
# 요청 payload(dict) -> 응답 payload(dict) 핸들러
#
# HTTP 전송 방식(BaseHTTPRequestHandler, WSGI 등)과 완전히 분리해 두면
# Vercel Python 런타임이 진입점(entrypoint)을 하나만 요구하더라도(api/index.py)
# 라우팅 방식만 바꿔서 재사용할 수 있다. api/index.py, scripts/dev_server.py가
# 이 두 함수를 호출한다.
# ---------------------------------------------------------------------------

def handle_recommend(payload):
    """POST /api (action="recommend") 처리. A1-2의 1차 추천 + 맛집 검색에 대응."""
    if not isinstance(payload, dict):
        raise ValidationError("요청 형식이 올바르지 않습니다.")

    travel_date = validate_date_str(payload.get("date"))
    preference = validate_preference(payload.get("preference"))

    cody_key, openai_key, kakao_key = load_api_keys()

    errors = []
    date_str = travel_date.isoformat()

    recommendation, key_source = request_recommendation(cody_key, openai_key, date_str, preference, errors)
    if recommendation is None:
        raise UpstreamError("1차 추천 생성에 실패했습니다.")

    recommendation = attach_restaurants(kakao_key, recommendation, errors)

    return {
        "recommended_cities": recommendation["recommended_cities"],
        "errors": errors,
        "ai_key_source": key_source,
    }


def handle_report(payload):
    """POST /api (action="report") 처리. A1-2의 리포트 생성에 대응."""
    travel_date, recommended_cities, errors = validate_report_request(payload)

    cody_key, openai_key, _ = load_api_keys()

    data, key_source = generate_report(cody_key, openai_key, travel_date.isoformat(), recommended_cities, errors)
    data["ai_key_source"] = key_source
    return data
