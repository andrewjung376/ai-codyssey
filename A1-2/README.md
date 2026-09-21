# 국내 여행 추천 프로그램

여행 날짜를 입력하면 LLM(OpenAI)이 여행지를 추천하고, Kakao Local API로 해당 지역의 맛집을 검색한 뒤, 두 결과를 종합해 최종 여행 리포트(Markdown)를 생성하는 CLI 프로그램이다.

## 개요

1. **[1/3]** OpenAI에 여행 날짜를 입력해 추천 지역/날씨/행사/추천 이유를 JSON으로 받는다.
2. **[2/3]** 추천된 지역을 기준으로 Kakao Local API에서 맛집 5곳을 검색한다.
3. **[3/3]** 1·2단계 결과를 종합해 OpenAI가 최종 여행 리포트를 Markdown으로 생성한다.
4. 원본 데이터(JSON)와 최종 리포트(Markdown)를 `results/` 폴더에 저장한다.

### 단계별 입력/출력 예시

**[1/3] 1차 추천 (`request_recommendation()`)**

- **구조화된 JSON 출력을 강제하는 이유**: LLM 응답을 자유 텍스트로 받으면 다음 단계(맛집 검색 API 입력, 리포트 생성 입력)로 넘길 값을 매번 사람이 읽고 추출해야 해 자동화가 불가능하다. `response_format={"type": "json_object"}`와 "반드시 이 4개 키만 포함해 출력해"라는 프롬프트로 스키마를 강제하면 ①파싱 안정성(코드가 `json.loads()`로 항상 같은 구조를 기대할 수 있음), ②재현성(실행할 때마다 값은 달라져도 키 구조는 고정됨), ③단계 간 연결 용이성(1단계 출력을 그대로 2·3단계 입력으로 사용 가능)을 얻는다. 스키마를 지키지 못하면 `PARSE_ERROR`로 기록하고 최대 1회 재시도한다 (`doc/faq.md` Q9, Q16 참고).

입력: 사용자가 입력한 날짜 문자열

```
"2026-03-15"
```

출력: 아래 4개 키를 가진 JSON

```json
{
  "recommended_city": "제주",
  "weather": "3월 중순 평균 15°C 내외, 온화한 날씨",
  "events": ["유채꽃 축제", "봄 시즌 지역 축제"],
  "reason": "3월 중순은 제주가 봄꽃을 즐기기 좋은 시기입니다. 항공/숙박도 성수기 대비 부담이 적고 야외 활동에 무리가 적습니다."
}
```

**[2/3] 맛집 검색 (`search_restaurants()`)**

- **메서드 선택 이유**: Kakao Local 키워드 검색은 데이터를 조회만 할 뿐 서버 상태를 바꾸지 않는 멱등 요청이므로 GET을 사용한다. 반면 OpenAI 추천/리포트 생성(1·3단계)은 매 요청마다 새로운 결과를 생성하며 파라미터가 프롬프트 형태로 길어질 수 있어 본문(body)에 담아 보내는 POST를 사용한다.
- **제약**: GET 요청의 파라미터(`query`, `size`)는 URL 쿼리 스트링에 그대로 실린다. 검색어가 비정상적으로 길면 URL 전체 길이 제약에 걸려 요청이 실패할 수 있으므로, 사용자 입력을 그대로 쓰지 않고 `f"{city} 맛집"` 형태로 짧게 구성해 전달한다.

입력: 1단계 출력의 `recommended_city`

```
"제주"
```

출력: 맛집 최대 5곳의 리스트 (0건이면 빈 리스트 `[]`)

```json
[
  {
    "name": "네거리식당",
    "address": "제주특별자치도 서귀포시 서문로29번길 20",
    "category": "음식점 > 한식 > 해물,생선",
    "url": "http://place.map.kakao.com/9733194",
    "x": 126.559290966856,
    "y": 33.2484915875436
  }
]
```

**[3/3] 최종 리포트 생성 (`generate_report()`)**

입력: 1단계 JSON + 2단계 맛집 리스트(0건일 수 있음)

```json
{
  "recommendation": { "recommended_city": "제주", "weather": "...", "events": ["..."], "reason": "..." },
  "restaurants": [ { "name": "네거리식당", "...": "..." } ]
}
```

출력: 아래 6개 섹션을 포함한 Markdown 텍스트

```markdown
# 2026-03-15 국내 여행 추천 리포트
## 추천 지역
## 추천 이유
## 날씨 요약
## 행사/축제
## 맛집 추천
## 1일 일정 제안
## 오류 요약(errors)
```

## 실행 방법

### 1. 가상환경 생성 및 활성화

**Windows PowerShell**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

### 3. API 키 설정

`.env.example`을 복사해 `.env` 파일을 만들고, 발급받은 키 값을 채운다.

```bash
cp .env.example .env
```

```
OPENAI_API_KEY=여기에_본인의_OpenAI_키
KAKAO_REST_API_KEY=여기에_본인의_Kakao_REST_API_키
```

- OpenAI API 키: https://platform.openai.com 에서 발급
- Kakao REST API 키: https://developers.kakao.com 에서 애플리케이션 생성 후 발급 (REST API 키 사용)

### 4. 프로그램 실행

```bash
python travel_planner.py -date "2026-03-15"
```

실행하면 아래와 같이 진행 로그가 출력된다.

```
[1/3] 1차 추천 생성 중(LLM)...
  - recommended_city: "제주"
[2/3] 맛집 검색 중(Kakao Local)...
  - 맛집 5곳 검색 완료
[3/3] 최종 리포트 생성 중(LLM)...
  - 리포트 생성 완료

완료! results/2026-03-15_travel_plan.md 를 확인하세요.
원본 데이터: results/2026-03-15_raw_data.json
```

## 결과물 확인 방법

프로그램 실행 후 `results/` 폴더에 다음 파일이 생성된다.

| 파일 | 내용 |
|---|---|
| `results/{date}_raw_data.json` | 1차 추천 JSON, 맛집 검색 결과, 오류 요약(`errors`) |
| `results/{date}_travel_plan.md` | 추천 지역/이유, 날씨, 행사, 맛집, 1일 일정, 오류 요약이 포함된 최종 리포트 |

맛집 검색이 0건이거나 Kakao API 인증(401/403) 오류가 발생해도 프로그램은 중단되지 않고, 해당 섹션을 "데이터 없음"으로 표기한 뒤 리포트 생성까지 계속 진행한다.

## 오류 처리

| 상황 | 동작 |
|---|---|
| API 키 미설정 (`OPENAI_API_KEY` 또는 `KAKAO_REST_API_KEY`) | 즉시 종료, 설정 방법 안내 출력 |
| Kakao Local 실패(네트워크/401/403) 또는 0건 | `errors`에 기록 후 "데이터 없음"으로 계속 진행 |
| OpenAI 1차 추천 JSON 파싱 실패 | 필수 키만 다시 JSON으로 출력하도록 프롬프트를 수정해 최대 1회 재시도 |

## 에러 경로 테스트 방법

정상 실행 외에, 아래 항목은 별도 방법으로 재현/검증한다.

### 1. 날짜 형식 오류 / API 키 미설정

정상적으로 발생시켜 확인한다.

```bash
# 날짜 형식 오류 → 사용법 출력 후 종료
python travel_planner.py -date "2026-13-40"

# API 키 미설정 → 안내 메시지 출력 후 종료
# (.env에서 키를 지우거나 이름을 바꾼 뒤 실행)
python travel_planner.py -date "2026-03-15"
```

### 2. 맛집 검색 0건 / LLM JSON 파싱 실패 재시도

이 두 경로는 정상적인 입력으로는 우연히 발생하기 어려워, `test_edge_cases.py`로 실제 API를 호출해 강제로 재현한다.

```bash
python test_edge_cases.py
```

- **케이스 1(맛집 0건)**: 존재할 수 없는 지명으로 Kakao Local API를 실제로 호출해 0건 응답을 유도하고, `search_restaurants()`가 `EMPTY_RESULT`를 기록하며 빈 리스트를 반환하는지 확인한다.
- **케이스 2(JSON 파싱 실패 재시도)**: 1차 요청에서 의도적으로 다른 스키마(`city`, `temp`)를 요구해 OpenAI가 필수 키 없는 JSON을 반환하게 한 뒤, `travel_planner.py`의 재시도 프롬프트(`build_recommendation_prompt(date, retry=True)`)로 2차 요청을 보내 필수 키 4개(`recommended_city`, `weather`, `events`, `reason`)를 모두 갖춘 JSON을 받는지 확인한다.

두 케이스 모두 `PASS` 문구가 출력되면 정상이며, `assert` 실패 시 예외가 발생한다. `travel_planner.py`의 프로덕션 코드는 수정하지 않고, 해당 파일의 함수를 그대로 불러와 검증한다.

## 보안 주의사항 (API 키 유출 방지)

- **API 키를 코드에 직접 작성하지 않는다.** `.env` 파일 또는 환경변수로만 관리한다.
- `.env` 파일은 `.gitignore`에 등록되어 있어 git에 커밋되지 않는다. 절대 수동으로 커밋하지 않는다.
- `results/` 폴더의 결과 파일이나 로그에는 키 값이 남지 않는다. 오류 메시지에도 키 값을 출력하지 않는다.
- 키를 공유해야 할 경우 `.env` 파일이 아니라 `.env.example`(키 이름만 있고 값은 비어 있음)을 공유한다.
- 실수로 키를 커밋했다면 즉시 해당 키를 재발급(폐기)하고 커밋 히스토리에서 제거해야 한다.

## 개발 환경

- Python 3.10 이상
- 의존성: `openai`, `requests`, `python-dotenv` (`requirements.txt` 참고)
