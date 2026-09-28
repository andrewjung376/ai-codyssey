"""AI여행추천(AI TripPick) 공용 로직.

A1-2(`travel_planner.py`)의 CLI 파이프라인(1차 추천 -> 맛집 검색 -> 리포트 생성)을
웹 서비스용으로 이식한 모듈이다. 파일명이 "_"로 시작하므로 Vercel이 별도의
API 엔드포인트로 노출하지 않고, recommend.py / report.py가 이 모듈을 가져다 쓴다.

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

OPENAI_MODEL = "gpt-4o-mini"
OPENAI_TIMEOUT_SECONDS = 25  # Vercel 함수 maxDuration(30초)보다 짧게 잡아 타임아웃을 서버가 직접 처리한다.

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
    openai_key = os.environ.get("OPENAI_API_KEY")
    kakao_key = os.environ.get("KAKAO_REST_API_KEY")

    missing = []
    if not openai_key:
        missing.append("OPENAI_API_KEY")
    if not kakao_key:
        missing.append("KAKAO_REST_API_KEY")

    if missing:
        # 키 값은 절대 로그/응답에 남기지 않고, 누락된 키 "이름"만 서버 로그에 남긴다.
        print(f"[config error] 다음 환경변수가 설정되지 않았습니다: {', '.join(missing)}")
        raise ConfigError("서비스 설정 오류입니다.")

    return openai_key, kakao_key


def get_openai_client(api_key):
    return OpenAI(api_key=api_key, timeout=OPENAI_TIMEOUT_SECONDS)


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


def request_recommendation(client, travel_date, preference, errors):
    messages = [{"role": "user", "content": build_recommendation_prompt(travel_date, preference)}]

    for attempt in range(2):
        content = None
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            validate_recommendation(data)
            return data
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
            return None
        except Exception as e:
            errors.append({
                "step": "recommendation",
                "type": "API_ERROR",
                "message": f"OpenAI 호출 실패: {e}",
            })
            return None

    return None


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


def generate_report(client, travel_date, recommended_cities, errors):
    prompt = build_report_prompt(travel_date, recommended_cities, errors)
    content = None
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        validate_report_response(data, len(recommended_cities))
        return data
    except (json.JSONDecodeError, ValueError) as e:
        preview = content[:RAW_RESPONSE_PREVIEW_LEN] if content else None
        raise UpstreamError(f"리포트 응답 형식이 올바르지 않습니다: {e}") from e
    except UpstreamError:
        raise
    except Exception as e:
        raise UpstreamError(f"OpenAI 호출 실패: {e}") from e
