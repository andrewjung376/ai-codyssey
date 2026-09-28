# AI여행추천 (AI TripPick)

여행 날짜를 입력하면 AI가 그 시기에 어울리는 국내 여행지 2~3곳을 추천하고, 카카오 로컬 API로 지역별 실제 맛집을 찾은 뒤, 지역별 1일 일정까지 정리해 주는 웹 서비스다.

- **배포 URL**: https://ai-codyssey.vercel.app
- **GitHub 저장소**: https://github.com/andrewjung376/ai-codyssey (이 폴더: `A1-3/`)

## 서비스 소개

- **목적**: 여행 갈 날짜는 정했지만 어디로 갈지 못 정한 사람에게, 시기(날씨·축제)에 맞는 국내 여행지와 실제 맛집, 1일 일정을 한 번에 추천한다.
- **타겟 사용자**: 여행 날짜는 정했지만 행선지를 못 정한 20~40대 직장인
- **핵심 기능**
  1. 날짜(+선택적 여행 취향) 기반 AI 여행지 추천 2~3곳
  2. 지역별 실제 맛집 검색(카카오맵 링크 포함)
  3. 지역별 1일 일정 제안
  4. 결과를 Markdown 리포트로 다운로드
  5. 같은 날짜로 재검색 시 브라우저 캐시를 재사용해 API 호출 절감
- 자세한 서비스 기획(목적/타겟/페이지 구성/AI 기능 입출력·실패 처리 기준)은 [`submission/service-plan.md`](submission/service-plan.md) 참고.

## 페이지 구성

단일 페이지(`index.html`) 안에서 해시 링크로 이동하는 4개 섹션(모바일은 햄버거 메뉴):

| 섹션 | 내용 |
|---|---|
| 홈(`#home`) | 서비스 소개, "여행지 추천받기" 버튼 |
| 이용 방법(`#how`) | 추천 → 맛집 → 일정 3단계 설명 |
| AI 플래너(`#planner`) | 입력 폼 + 추천 결과(핵심 AI 기능) |
| FAQ(`#faq`) | 데이터 출처, 한계, 재추천 방법 안내 |

## 기술 스택

- **프론트엔드**: 순수 HTML / CSS / JavaScript (프레임워크 미사용)
- **백엔드**: Vercel Serverless Functions (Python, `api/`)
- **AI API**: [Codyssey 과정 제공 OpenAI 호환 프록시](https://copa.codyssey.kr)(`gpt-5-mini`, 1순위) → 실패 시 OpenAI 공식 API(`gpt-4o-mini`, 2순위 폴백)
- **외부 API**: Kakao Local API (맛집 검색)
- **배포**: Vercel (GitHub 연동, 자동 배포)

## 프로젝트 구조

```
A1-3/
├─ index.html            # 메인 페이지 (홈/이용방법/AI플래너/FAQ)
├─ css/style.css         # 반응형 스타일(모바일 우선, 768px/1024px 분기), 다크모드
├─ js/app.js             # 네비게이션, 폼 검증, fetch 호출, 결과 렌더링, 캐시
├─ images/               # 파비콘 등 정적 이미지
├─ api/
│  ├─ index.py           # 단일 진입점 (POST /api, action으로 recommend/report 라우팅)
│  ├─ _core.py           # 검증·프롬프트·AI/Kakao 호출 등 핵심 로직
│  └─ _http.py           # HTTP 요청 파싱/응답/예외→상태코드 매핑 공통 로직
├─ requirements.txt      # openai, requests, python-dotenv
├─ vercel.json           # Serverless Function 설정(maxDuration)
├─ .env.example          # 필요한 환경 변수 이름
└─ submission/           # 제출 증빙(서비스 기획서, 스크린샷, AI 사용 로그)
```

> `api/index.py` 하나만 있는 이유: Vercel Python 런타임이 프로젝트를 하나의 애플리케이션으로 빌드하며 진입점을 하나만 자동 인식하기 때문이다. 파일마다 별도 엔드포인트를 두던 초기 구조에서 이 방식으로 바꾼 배경은 아래 "배포 중 겪은 문제" 참고.

## AI 기능 (입력 → 출력 → 실패 처리)

| 구분 | 내용 |
|---|---|
| 입력 | 여행 날짜(필수, 오늘 이후) + 여행 취향(선택, 200자 이내) |
| 출력 | 여행지 2~3곳(날씨/행사/추천 이유), 지역별 맛집 최대 5곳(카카오맵 링크 포함), 지역별 1일 일정(오전/오후/저녁), Markdown 리포트 다운로드 |
| 실패 처리 | 빈 입력·형식 오류 → 400 인라인 안내 / API 오류 → 502 + 재시도 버튼 / 8초 경과 시 지연 안내 / 30초~55초 경과 시 타임아웃 안내 |

`POST /api`에 `{"action": "recommend", ...}` 또는 `{"action": "report", ...}`로 요청하면, 어떤 AI 키 경로(Codyssey 프록시 또는 OpenAI 폴백)로 응답했는지 `ai_key_source` 값이 함께 오고, 화면 결과에도 표시된다.

## 로컬 실행 방법

### 1. 가상환경 생성 및 의존성 설치

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # Windows
# source .venv/bin/activate       # macOS/Linux

pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env.example`을 복사해 `.env`를 만들고 값을 채운다.

```bash
cp .env.example .env
```

```
CODY_OPENAI_API_KEY=여기에_Codyssey_프록시용_키
OPENAI_API_KEY=여기에_OpenAI_키(폴백용, 선택)
KAKAO_REST_API_KEY=여기에_Kakao_REST_API_키
```

- `CODY_OPENAI_API_KEY`, `OPENAI_API_KEY` 중 **최소 하나**는 있어야 한다 (하나만 있어도 동작).
- Kakao REST API 키: https://developers.kakao.com 에서 애플리케이션 생성 후 발급(REST API 키 사용, 카카오맵/로컬 서비스 활성화 필요)

### 3. 로컬 서버 실행

정식 배포 환경은 Vercel Serverless Functions이지만, 로컬에서는 Vercel 계정 로그인 없이도 동일한 `api/` 로직을 그대로 실행하는 개발 서버 스크립트를 쓴다.

```bash
python scripts/dev_server.py 3000
```

브라우저에서 http://localhost:3000 접속.

## 배포 방법 (Vercel)

1. Vercel 대시보드에서 GitHub 저장소(`ai-codyssey`) 연결
2. **Root Directory**를 `A1-3`으로 지정
3. **Framework Preset**을 `Other`로 지정 (자동 감지된 `Python` 프리셋을 쓰면 정적 파일까지 Python 함수로 라우팅되어 실패함 — 아래 참고)
4. **Environment Variables**에 `CODY_OPENAI_API_KEY`, `OPENAI_API_KEY`, `KAKAO_REST_API_KEY` 등록 (Production 환경 체크)
5. Deploy

## 배포 중 겪은 문제와 해결 (요약)

배포 과정에서 실제로 겪은 오류와 해결 방법을 기록한다. 자세한 원인 분석은 이 프로젝트의 개발 대화 로그([`submission/ai-log/`](submission/ai-log/)) 참고.

| 문제 | 원인 | 해결 |
|---|---|---|
| 빌드 실패: "No python entrypoint found ... found potential entrypoints" | `api/`에 `handler`를 내보내는 파일이 2개(`recommend.py`, `report.py`)라 Vercel이 진입점을 하나로 특정하지 못함 | `api/index.py` 하나로 통합, 요청 본문의 `action` 필드로 내부 라우팅 |
| 배포 후 모든 요청 500: `ModuleNotFoundError: No module named '_core'` | Vercel이 `api/index.py`를 개별 모듈로 로드하며 같은 폴더를 `sys.path`에 자동으로 넣어주지 않음 | `api/index.py` 상단에서 자기 자신의 디렉터리를 `sys.path`에 직접 추가 |
| `GET /`까지 Python 함수로 라우팅되어 실패 | `requirements.txt` 존재만으로 Vercel이 "Python 프레임워크"로 자동 인식해, 정적 파일까지 전부 그 함수로 밀어넣음 | 프로젝트 설정에서 **Framework Preset을 `Other`로 변경** |
| `POST /api` 504 (60초 타임아웃) | 1순위 AI 프록시가 느릴 때(~28초) 검증 실패 재시도가 프록시를 한 번 더 시도해 예산 초과 | 재시도 시에는 프록시를 건너뛰고 바로 폴백(OpenAI)으로 감 |
| 다운로드 리포트에 맛집 링크 누락 | 다운로드용 Markdown 전체를 AI 자유 텍스트로 생성해 링크가 가끔 빠짐 | AI에는 요약/일정만 요청하고, Markdown은 서버가 보유한 실제 카카오 데이터로 직접 조립 |

## 오류 처리 요약

| 상황 | 동작 |
|---|---|
| 필수 입력 누락/형식 오류 | 프론트에서 인라인 오류 메시지 (400) |
| API 키 미설정 | 500 + "서비스 설정 오류입니다" (키 값은 로그에도 남기지 않음) |
| AI 응답 실패(양쪽 경로 모두) | 502 + 재시도 버튼 |
| Kakao 검색 실패/0건 | 해당 지역만 "데이터 없음"으로 표시, 나머지는 정상 진행 |
| 응답 지연 | 8초 경과 시 지연 안내, 55초 경과 시 타임아웃 안내 |

## 보안 주의사항

- API 키는 코드에 직접 작성하지 않고 환경 변수로만 관리한다.
- `.env` 파일은 `.gitignore`에 등록되어 있어 git에 커밋되지 않는다.
- 키가 노출되었다면 즉시 재발급하고 커밋 히스토리도 정리한다.

## 개발 환경

- Python 3.10 이상
- 의존성: `openai`, `requests`, `python-dotenv` (`requirements.txt` 참고)
- AI 코딩 도구를 활용해 개발했다. 사용 과정은 [`submission/ai-log/`](submission/ai-log/) 참고.
