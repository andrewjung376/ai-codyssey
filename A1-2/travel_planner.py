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


def parse_args():
    parser = argparse.ArgumentParser(
        description="여행 날짜를 입력받아 국내 여행지를 추천하고 맛집 정보를 담은 리포트를 생성한다."
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
    if retry:
        return (
            f"{date}에 여행하기 좋은 국내 지역을 추천해줘. "
            "반드시 아래 4개의 키만 포함한 JSON 객체 하나만 출력해. "
            "다른 설명, 마크다운, 코드블록 없이 순수 JSON만 출력해.\n"
            '{"recommended_city": "", "weather": "", "events": [], "reason": ""}'
        )
    return (
        f"{date}에 여행하기 좋은 국내 지역을 한 곳 추천해줘.\n"
        "아래 JSON 스키마를 반드시 지켜서 출력해.\n"
        "- recommended_city: string (예: \"제주\", \"강릉\")\n"
        "- weather: string (해당 시기 일반적 날씨 요약)\n"
        "- events: array of string (행사/축제 후보 1~3개)\n"
        "- reason: string (추천 근거 2~4문장)\n"
        "실제 정확한 예보/행사 데이터가 없다면 그 시기의 일반적인 경향으로 서술해.\n"
        "모든 텍스트 값은 한글로만 작성해. 한자, 일본어 등 다른 문자를 섞지 마."
    )


def request_recommendation(client, date, errors):
    messages = [{"role": "user", "content": build_recommendation_prompt(date)}]

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            data = json.loads(content)

            required_keys = {"recommended_city", "weather", "events", "reason"}
            if not required_keys.issubset(data.keys()):
                raise ValueError(f"필수 키 누락: {required_keys - data.keys()}")

            return data
        except (json.JSONDecodeError, ValueError) as e:
            errors.append({
                "step": "recommendation",
                "type": "PARSE_ERROR",
                "message": f"JSON 파싱 실패 (시도 {attempt + 1}/2): {e}",
            })
            if attempt == 0:
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
        response = requests.get(KAKAO_KEYWORD_SEARCH_URL, headers=headers, params=params, timeout=10)

        if response.status_code in (401, 403):
            errors.append({
                "step": "place_search",
                "type": "AUTH_ERROR",
                "message": f"HTTP {response.status_code}: {response.text}",
            })
            return []

        response.raise_for_status()
        documents = response.json().get("documents", [])

        if not documents:
            errors.append({
                "step": "place_search",
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
            "type": "NETWORK_ERROR",
            "message": str(e),
        })
        return []


def build_report_prompt(date, recommendation, restaurants, errors):
    restaurant_text = (
        json.dumps(restaurants, ensure_ascii=False, indent=2)
        if restaurants
        else "데이터 없음 (장소 검색 결과 0건 또는 검색 실패)"
    )

    return (
        f"아래 정보를 바탕으로 {date} 국내 여행 추천 리포트를 Markdown으로 작성해줘.\n\n"
        f"[1차 추천 정보]\n{json.dumps(recommendation, ensure_ascii=False, indent=2)}\n\n"
        f"[맛집 목록]\n{restaurant_text}\n\n"
        "리포트는 반드시 아래 구조를 따르고, 순수 Markdown 텍스트만 출력해 (코드블록으로 감싸지 마).\n"
        "모든 텍스트는 한글로만 작성해 (한자, 일본어 등 다른 문자를 섞지 마):\n"
        f"# {date} 국내 여행 추천 리포트\n"
        "## 추천 지역\n"
        "## 추천 이유\n"
        "## 날씨 요약\n"
        "## 행사/축제\n"
        "## 맛집 추천\n"
        "(맛집 데이터가 없으면 \"데이터 없음\"이라고 표기)\n"
        "## 1일 일정 제안\n"
        "(오전/오후/저녁 수준으로 간단히)\n"
        "## 오류 요약(errors)\n"
        f"(아래 오류 목록을 표기, 없으면 \"오류 없음\"이라고 표기)\n{json.dumps(errors, ensure_ascii=False)}"
    )


def generate_report(client, date, recommendation, restaurants, errors):
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": build_report_prompt(date, recommendation, restaurants, errors)}],
        )
        return response.choices[0].message.content
    except Exception as e:
        errors.append({
            "step": "report",
            "type": "API_ERROR",
            "message": f"OpenAI 호출 실패: {e}",
        })
        return None


def save_results(date, recommendation, restaurants, errors, report_text):
    os.makedirs(RESULTS_DIR, exist_ok=True)

    raw_data = {
        "date": date,
        "recommendation": recommendation,
        "restaurants": restaurants,
        "errors": errors,
    }
    json_path = os.path.join(RESULTS_DIR, f"{date}_raw_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)

    md_path = os.path.join(RESULTS_DIR, f"{date}_travel_plan.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_text or "# 리포트 생성 실패\n\n리포트 생성 중 오류가 발생했습니다.")

    return json_path, md_path


def main():
    date = parse_args()
    openai_key, kakao_key = load_api_keys()
    client = OpenAI(api_key=openai_key)
    errors = []

    print("[1/3] 1차 추천 생성 중(LLM)...")
    recommendation = request_recommendation(client, date, errors)
    if recommendation is None:
        print("  - 오류: 1차 추천 생성에 실패했습니다. 프로그램을 종료합니다.", file=sys.stderr)
        for err in errors:
            print(f"    · {err['type']}: {err['message']}", file=sys.stderr)
        sys.exit(1)
    print(f"  - recommended_city: \"{recommendation.get('recommended_city')}\"")

    print("[2/3] 맛집 검색 중(Kakao Local)...")
    restaurants = search_restaurants(kakao_key, recommendation["recommended_city"], errors)
    if restaurants:
        print(f"  - 맛집 {len(restaurants)}곳 검색 완료")
    else:
        print("  - 데이터 없음 (검색 결과 0건 또는 실패). '데이터 없음'으로 다음 단계 진행합니다.")

    print("[3/3] 최종 리포트 생성 중(LLM)...")
    report_text = generate_report(client, date, recommendation, restaurants, errors)
    if report_text:
        print("  - 리포트 생성 완료")
    else:
        print("  - 오류: 리포트 생성에 실패했습니다. 실패 안내 문서를 저장합니다.")

    json_path, md_path = save_results(date, recommendation, restaurants, errors, report_text)
    print(f"\n완료! {md_path} 를 확인하세요.")
    print(f"원본 데이터: {json_path}")


if __name__ == "__main__":
    main()
