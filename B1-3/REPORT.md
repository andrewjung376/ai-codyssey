# 노코드 자동화 도구 비교 및 자유 주제 자동화 보고서

> 상태: 구현, 분기별 실행 검증 및 증빙 수집 완료

## 1. 과제 개요

이 보고서는 동일한 고객 문의 분류 워크플로우를 n8n과 Make로 구현해 비교하고, n8n으로 웹 서비스 상태 점검 자동화를 구현한 결과를 정리한다.

## 2. 핵심 개념

### Trigger

자동화를 시작하는 사건이다. 프로젝트 1에서는 고객 문의가 Webhook으로 들어오는 사건, 프로젝트 2에서는 설정한 시간이 되는 사건이 Trigger다.

### Action

Trigger 이후 데이터를 정리하거나 외부 작업을 수행하는 단계다. 입력 정리, HTTP 요청, 결과 생성, 응답 반환, 이력 저장 등이 해당한다.

### 조건 분기

입력이나 처리 결과에 따라 서로 다른 경로를 실행하는 기능이다. n8n에서는 IF, Make에서는 Router와 Filter를 사용한다.

## 3. 프로젝트 1 — n8n vs Make

### 3.1 자동화 업무

고객 문의를 Webhook으로 접수하고 우선순위에 따라 긴급/일반으로 분류한 후 서로 다른 SLA가 포함된 접수 결과를 반환한다.

### 3.2 공통 워크플로우

Webhook → 입력값 정리 → 긴급 여부 분기 → 분기별 결과 생성 → JSON 응답

세부 설계는 `docs/project1-design.md`에 정리했다.

### 3.3 n8n 구현 결과

n8n 2.25.1 self-hosted 환경에 7개 노드로 구현하고 게시했다.

- Webhook → Edit Fields → IF → 분기별 Edit Fields → Respond to Webhook
- 긴급 입력 `T-001`: `URGENT`, `1시간 이내` 응답 성공
- 일반 입력 `T-002`: `NORMAL`, `24시간 이내` 응답 성공
- 테스트 모드와 게시 후 운영 Webhook에서 모두 검증
- 운영 테스트 2건 모두 `Passed=True`

증빙: `captures/p1-n8n-urgent-result.png`, `captures/p1-n8n-normal-result.png`, `captures/p1-n8n-production-history.png`, `captures/p1-n8n-production-test.txt`

### 3.4 Make 구현 결과

Make Free 환경에 7개 모듈로 같은 논리 구조를 구현하고 즉시 실행 시나리오로 활성화했다.

- Custom webhook → Set multiple variables → Router
- 긴급 경로: `priority = urgent` Filter → Set multiple variables → Webhook response
- 일반 경로: fallback → Set multiple variables → Webhook response
- 긴급 입력 `T-001`: `URGENT`, `1시간 이내` JSON 응답 성공
- 일반 입력 `T-002`: `NORMAL`, `24시간 이내` JSON 응답 성공
- 최종 운영 실행 2건 모두 `Success`, 실행당 4 credits 사용

초기 테스트 3건은 수동 실행 대기 세션과 활성화 시점이 겹쳐 `Warning`으로 기록됐다. 실행 상태를 정리하고 시나리오를 활성화한 뒤 최종 테스트 2건은 정상 완료됐으며 최종 증빙에는 성공 실행을 사용한다.

증빙: `captures/p1-make-scenario.png`, `captures/p1-make-urgent-result.png`, `captures/p1-make-normal-result.png`, `captures/p1-make-execution-history.png`

### 3.5 비교 분석

| 비교 항목 | n8n | Make |
|---|---|---|
| UI/UX | 노드와 연결선 중심으로 데이터 흐름이 선명하다. | 큰 원형 모듈과 Router 경로로 전체 구조를 직관적으로 보여준다. |
| 초기 설정 | self-hosting 환경과 실행 서버가 필요하다. | 가입 후 브라우저에서 바로 사용할 수 있다. |
| Webhook 구성 | 테스트 URL과 운영 URL이 구분된다. | 하나의 Custom Webhook을 샘플 감지와 운영에 사용한다. |
| 조건 분기 | IF의 true/false 출력 | Router와 경로별 Filter |
| 데이터 매핑 | 표현식으로 JSON 필드를 직접 참조한다. | 매핑 패널에서 이전 모듈의 필드를 토큰으로 선택한다. |
| 실행 로그 | 실행별로 노드 입력·출력과 실제 통과 경로가 표시된다. | History와 Simple/Advanced log에서 모듈별 통과 여부를 확인한다. |
| 무료 범위 | self-hosted Community Edition 사용 | 월 1,000 credits의 Free 플랜 사용 |
| 운영 통제권 | 로컬 환경과 데이터를 직접 관리 | Make가 호스팅과 운영을 관리 |
| 실행 비용 단위 | 자체 서버 자원을 사용하며 이 과제에서는 실행별 과금이 없다. | 최종 워크플로우는 실행 1회당 4 credits를 사용했다. |
| 문제 해결 | 노드 출력과 상태 코드를 직접 확인하기 쉽다. | 활성 상태와 Webhook 큐를 함께 확인해야 한다. |

### 3.6 장단점과 적합한 상황

#### n8n

장점은 self-hosting, 세밀한 실행 데이터, 표현식 자유도, 내부 Data Table이다. 서버 운영이 가능하고 데이터 통제나 복잡한 처리 흐름이 중요한 업무에 적합하다. 단점은 설치·업데이트·가용성을 직접 관리해야 하고 처음 사용하는 사람에게 설정 항목이 많게 느껴질 수 있다는 점이다.

#### Make

장점은 별도 설치 없이 시작할 수 있고 Router와 매핑 패널이 시각적이라는 점이다. SaaS 간 연결을 빠르게 구성하려는 개인이나 팀에 적합하다. 단점은 모듈 실행마다 credits가 사용되고 수동 실행·활성화·Webhook 큐의 상태를 구분해 관리해야 한다는 점이다.

빠른 SaaS 연결과 낮은 운영 부담이 우선이면 Make가 적합하다. 데이터 통제, 확장성, 복잡한 로직과 자체 운영이 중요하면 n8n이 더 적합하다.

## 4. 프로젝트 2 — n8n 웹 서비스 자동 상태 점검

### 4.1 반복 업무와 선정 이유

운영자가 정기적으로 서비스 주소를 열어 상태를 확인하고 기록하는 업무를 자동화한다. n8n은 정기 실행, HTTP 요청, 조건 분기, 내부 이력 저장을 한 화면에서 구성할 수 있고 self-hosting이 가능해 선정했다.

### 4.2 워크플로우

Schedule Trigger → HTTP Request → 상태 코드 분기 → 결과 생성 → Data Table 저장

세부 설계는 `docs/project2-design.md`에 정리했다.

### 4.3 구현 및 실행 결과

7개 노드로 구현하고 15분 간격 Schedule Trigger를 게시했다.

- Schedule Trigger → HTTP Request → IF → 분기별 Edit Fields → Data Table
- 정상 점검: `/healthz` 응답 200 → `NORMAL` 저장
- 장애 점검: 존재하지 않는 Webhook 경로 응답 404 → `FAILURE` 저장
- 장애 검증 후 점검 URL을 `/healthz`로 복구
- Data Table 최종 검증 시 정상 3건과 장애 1건 저장 확인

증빙: `captures/p2-n8n-workflow.png`, `captures/p2-n8n-published.png`, `captures/p2-n8n-success-result.png`, `captures/p2-n8n-failure-result.png`, `captures/p2-n8n-data-table.png`

## 5. 보안 및 비용

- 모든 테스트 데이터는 가상 고객 정보로 작성한다.
- Webhook 운영 URL과 계정 정보는 캡처 시 마스킹한다.
- n8n은 로컬 Community Edition, Make는 Free 플랜 범위에서 사용한다.
- 유료 기능은 기본 구현에 사용하지 않는다.

## 6. 결론

두 도구 모두 동일한 Trigger, 입력 정리, 조건 분기, 분기별 결과 생성, 응답 반환 구조를 실제로 구현할 수 있었다. n8n은 실행 데이터와 운영 통제에서 강점이 있었고 Make는 설치 없는 시작과 시각적 매핑에서 강점이 있었다. 프로젝트 2에서는 n8n의 Schedule Trigger와 Data Table을 사용해 정기 점검, 정상/장애 분기, 이력 저장까지 하나의 자동 파이프라인으로 완성했다.

## 참고 자료

- https://docs.n8n.io/
- https://help.make.com/
- https://www.make.com/en/pricing
