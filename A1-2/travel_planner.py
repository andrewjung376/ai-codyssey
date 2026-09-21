import argparse
import json
import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv
from openai import OpenAI

OPENAI_MODEL = "gpt-4o-mini"
KAKAO_KEYWORD_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
RESTAURANT_COUNT = 5
RESULTS_DIR = "results"
MIN_CITIES = 2
MAX_CITIES = 3
NO_DATA_TEXT = "데이터 없음"
RAW_RESPONSE_PREVIEW_LEN = 200


def parse_args():
    parser = argparse.ArgumentParser(
        description="여행 날짜를 입력받아 국내 여행지 2~3곳을 추천하고 지역별 맛집 정보를 담은 리포트를 생성한다."
    )
    parser.add_argument(
        "-date",
        required=True,
        help='여행 날짜. 형식: "YYYY-MM-DD" (연 4자리-월 2자리-일 2자리), 예: "2026-03-15"',
    )
    args = parser.parse_args()

    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        parser.print_usage(sys.stderr)
        print(f'오류: 날짜 형식이 올바르지 않습니다. 입력값: "{args.date}"', file=sys.stderr)
        print('허용 형식: "YYYY-MM-DD" (연 4자리-월 2자리-일 2자리)', file=sys.stderr)
        print('예) -date "2026-03-15"', file=sys.stderr)
        sys.exit(1)

    return args.date


def load_api_keys():
    load_dotenv()
    openai_key = os.getenv("OPENAI_API_KEY")
    kakao_key = os.getenv("KAKAO_REST_API_KEY")

    missing = []
    if not openai_key:
        missing.append("OPENAI_API_KEY")
    if not kakao_key:
        missing.append("KAKAO_REST_API_KEY")

    if missing:
        print(f"오류: 다음 환경변수가 설정되지 않았습니다: {', '.join(missing)}", file=sys.stderr)
        print("설정 방법:", file=sys.stderr)
        print('  1) 프로젝트 루트에 ".env" 파일을 만들고 아래 형식으로 키를 작성한다.', file=sys.stderr)
        print("     OPENAI_API_KEY=your_key_here", file=sys.stderr)
        print("     KAKAO_REST_API_KEY=your_key_here", file=sys.stderr)
        print("  2) 또는 터미널에서 환경변수로 직접 설정한다. (README.md 참고)", file=sys.stderr)
        sys.exit(1)

    return openai_key, kakao_key


def build_recommendation_prompt(date, retry=False):
    schema_hint = (
        '{"recommended_cities": ['
        '{"city": "", "weather": "", "events": [], "reason": ""}, '
        '{"city": "", "weather": "", "events": [], "reason": ""}'
        ']}'
    )
    if retry:
        return (
            f"{date}에 여행하기 좋은 국내 지역을 서로 다른 {MIN_CITIES}~{MAX_CITIES}곳 추천해줘. "
            "반드시 아래 형태의 JSON 객체 하나만 출력해. recommended_cities는 배열이고, "
            "배열의 각 항목은 city, weather, events, reason 4개 키만 가져야 해. "
            "다른 설명, 마크다운, 코드블록 없이 순수 JSON만 출력해.\n"
            f"{schema_hint}"
        )
    return (
        f"{date}에 여행하기 좋은 국내 지역을 서로 다른 {MIN_CITIES}~{MAX_CITIES}곳 추천해줘.\n"
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
    if "recommended_cities" not in data:
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


def request_recommendation(client, date, errors):
    messages = [{"role": "user", "content": build_recommendation_prompt(date)}]

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
                print(f"  - 재시도 사유: {e} → 필수 키만 다시 요청합니다.")
                messages = [{"role": "user", "content": build_recommendation_prompt(date, retry=True)}]
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


def search_restaurants(kakao_key, city, errors):
    headers = {"Authorization": f"KakaoAK {kakao_key}"}
    params = {"query": f"{city} 맛집", "size": RESTAURANT_COUNT}

    try:
        # Kakao Local 키워드 검색은 GET만 지원하는 조회 전용 API라 요청 파라미터가
        # URL 쿼리 스트링으로 노출된다. 검색어가 매우 길면 URL 길이 제약에 걸릴 수 있다.
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
                "x": float(doc["x"]) if doc.get("x") else None,
                "y": float(doc["y"]) if doc.get("y") else None,
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


def search_restaurants_by_city(kakao_key, recommendation, errors):
    """추천된 지역마다 맛집을 검색해 {city: [restaurant, ...]} 형태로 반환한다."""
    restaurants_by_city = {}
    for city_info in recommendation["recommended_cities"]:
        city = city_info["city"]
        restaurants = search_restaurants(kakao_key, city, errors)
        restaurants_by_city[city] = restaurants
        if restaurants:
            print(f"  - [{city}] 맛집 {len(restaurants)}곳 검색 완료")
        else:
            print(f"  - [{city}] {NO_DATA_TEXT} (검색 결과 0건 또는 실패)")
    return restaurants_by_city


def build_report_prompt(date, recommendation, restaurants_by_city, errors):
    restaurants_text = json.dumps(restaurants_by_city, ensure_ascii=False, indent=2)

    return (
        f"아래 정보를 바탕으로 {date} 국내 여행 추천 리포트를 Markdown으로 작성해줘.\n"
        f"추천 지역은 총 {len(recommendation['recommended_cities'])}곳이며, 리포트는 지역별로 구분해서 정리해야 해.\n\n"
        f"[지역별 추천 정보]\n{json.dumps(recommendation, ensure_ascii=False, indent=2)}\n\n"
        f"[지역별 맛집 목록] (키: 지역명, 값: 맛집 리스트, 빈 리스트면 \"{NO_DATA_TEXT}\")\n{restaurants_text}\n\n"
        "리포트는 반드시 아래 구조를 따르고, 순수 Markdown 텍스트만 출력해 (코드블록으로 감싸지 마).\n"
        "모든 텍스트는 한글로만 작성해 (한자, 일본어 등 다른 문자를 섞지 마):\n"
        f"# {date} 국내 여행 추천 리포트\n"
        "## 지역별 추천\n"
        "(추천된 지역 수만큼 아래 소제목을 반복)\n"
        "### {지역명}\n"
        "- 추천 이유\n"
        "- 날씨 요약\n"
        "- 행사/축제\n"
        f"- 맛집 추천 (맛집 데이터가 없으면 \"{NO_DATA_TEXT}\"라고 표기)\n"
        "- 1일 일정 제안 (오전/오후/저녁 수준으로 간단히)\n"
        "## 오류 요약(errors)\n"
        f"(아래 오류 목록을 표기, 없으면 \"오류 없음\"이라고 표기)\n{json.dumps(errors, ensure_ascii=False)}"
    )


def generate_report(client, date, recommendation, restaurants_by_city, errors):
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{
                "role": "user",
                "content": build_report_prompt(date, recommendation, restaurants_by_city, errors),
            }],
        )
        return response.choices[0].message.content
    except Exception as e:
        errors.append({
            "step": "report",
            "type": "API_ERROR",
            "message": f"OpenAI 호출 실패: {e}",
        })
        return None


def get_result_paths(date):
    json_path = os.path.join(RESULTS_DIR, f"{date}_raw_data.json")
    md_path = os.path.join(RESULTS_DIR, f"{date}_travel_plan.md")
    return json_path, md_path


def load_cached_raw_data(json_path):
    """같은 -date로 이미 저장된 원본 JSON이 있으면 읽어 재사용한다.

    project.md 보너스 과제(결과 캐싱): 캐시가 있으면 LLM 1차 추천과
    Kakao 맛집 검색 API 호출을 건너뛰고, 리포트만 다시 생성한다.
    파일이 없거나 형식이 손상된 경우 None을 반환해 정상적으로 새로 조회하게 한다.
    """
    if not os.path.exists(json_path):
        return None

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        recommendation = data["recommendation"]
        validate_recommendation(recommendation)
        restaurants_by_city = {item["city"]: item["items"] for item in data["restaurants"]}
        errors = list(data.get("errors", []))
        return recommendation, restaurants_by_city, errors
    except (json.JSONDecodeError, KeyError, ValueError, OSError):
        return None


def save_results(date, recommendation, restaurants_by_city, errors, report_text, skip_raw_write=False):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    json_path, md_path = get_result_paths(date)

    if not skip_raw_write:
        raw_data = {
            "date": date,
            "recommendation": recommendation,
            "restaurants": [
                {"city": city, "items": items}
                for city, items in restaurants_by_city.items()
            ],
            "errors": errors,
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_text or "# 리포트 생성 실패\n\n리포트 생성 중 오류가 발생했습니다.")

    return json_path, md_path


def main():
    date = parse_args()
    openai_key, kakao_key = load_api_keys()
    client = OpenAI(api_key=openai_key)

    json_path, _ = get_result_paths(date)
    cached = load_cached_raw_data(json_path)

    if cached:
        recommendation, restaurants_by_city, errors = cached
        cities = [c["city"] for c in recommendation["recommended_cities"]]
        print(f"[캐시 발견] {json_path} 를 재사용합니다. 1~2단계(LLM 추천/맛집 검색) API 호출을 건너뜁니다.")
        print(f"  - recommended_cities: {cities}")
    else:
        errors = []

        print("[1/3] 1차 추천 생성 중(LLM)...")
        recommendation = request_recommendation(client, date, errors)
        if recommendation is None:
            print("  - 오류: 1차 추천 생성에 실패했습니다. 프로그램을 종료합니다.", file=sys.stderr)
            for err in errors:
                print(f"    · {err['type']}: {err['message']}", file=sys.stderr)
            sys.exit(1)
        cities = [c["city"] for c in recommendation["recommended_cities"]]
        print(f"  - recommended_cities: {cities}")

        print("[2/3] 맛집 검색 중(Kakao Local)...")
        restaurants_by_city = search_restaurants_by_city(kakao_key, recommendation, errors)

    print("[3/3] 최종 리포트 생성 중(LLM)...")
    report_text = generate_report(client, date, recommendation, restaurants_by_city, errors)
    if report_text:
        print("  - 리포트 생성 완료")
    else:
        print("  - 오류: 리포트 생성에 실패했습니다. 실패 안내 문서를 저장합니다.")

    json_path, md_path = save_results(
        date, recommendation, restaurants_by_city, errors, report_text, skip_raw_write=bool(cached)
    )
    print(f"\n완료! {md_path} 를 확인하세요.")
    print(f"원본 데이터: {json_path}")


if __name__ == "__main__":
    main()
