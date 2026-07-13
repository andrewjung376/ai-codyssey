# 노코드 자동화 과제 작업 계획

## 확정 도구

- 프로젝트 1: n8n Community Edition vs Make Free
- 프로젝트 2: n8n Community Edition

## 확정 주제

### 프로젝트 1 — 고객 문의 우선순위 자동 분류 및 응답

HTTP 요청으로 들어온 고객 문의를 `긴급`과 `일반`으로 나누고, 분기별 처리 결과를 만들어 즉시 JSON으로 응답한다.

두 도구에서 다음 논리 구조를 동일하게 유지한다.

1. Webhook Trigger
2. 입력값 정리 및 접수 정보 생성
3. 우선순위 조건 분기
4. 분기별 처리 메시지 생성
5. Webhook 응답 반환

### 프로젝트 2 — 웹 서비스 자동 상태 점검 및 이력 기록

n8n이 일정 간격으로 점검 URL을 호출하고 HTTP 상태에 따라 `정상`과 `장애`로 분기한 다음 점검 이력을 Data Table에 저장한다.

## 실행 단계

1. n8n Community Edition을 Docker로 로컬 실행한다.
2. 프로젝트 1 n8n 워크플로우를 구현한다.
3. 긴급/일반 테스트 데이터를 각각 전송해 두 분기를 검증한다.
4. Make Free 계정에서 같은 구조의 시나리오를 구현한다.
5. 같은 테스트 데이터를 사용해 Make의 두 분기를 검증한다.
6. 프로젝트 2 n8n 워크플로우와 점검 이력 테이블을 구현한다.
7. 정상 URL과 실패 URL을 각각 사용해 두 분기를 검증한다.
8. 요구되는 구성 화면, 설정 화면, 실행 로그, 결과 화면을 캡처한다.
9. n8n과 Make를 최소 7개 항목으로 비교 분석한다.
10. 민감정보를 점검하고 최종 Markdown 보고서를 완성한다.

## 완료 기준

- 두 프로젝트 모두 실제로 실행된다.
- 각 프로젝트에 Trigger 1개, Action 2개 이상, 조건 분기 1개 이상이 있다.
- 모든 분기 경로가 최소 한 번 성공적으로 실행된 증거가 있다.
- 프로젝트 1의 두 도구가 같은 입력과 조건으로 비교된다.
- 스크린샷과 문서에 Webhook URL 전체, 이메일, 토큰 등 민감정보가 노출되지 않는다.

## 비용 정책

- n8n은 로컬 self-hosted Community Edition을 사용한다.
- Make는 Free 플랜 범위에서 구현한다.
- Make Free는 2026-07-13 공식 가격표 기준 월 1,000 credits, Router/Filter를 제공한다.
- 이번 테스트는 소량 실행이므로 무료 범위 내에서 충분하다.

## 공식 참고 자료

- n8n Docker 설치: https://docs.n8n.io/hosting/installation/docker/
- n8n Webhook: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/
- n8n IF: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.if/
- n8n Schedule Trigger: https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.scheduletrigger/
- Make Webhooks: https://help.make.com/webhooks
- Make Router: https://help.make.com/router
- Make 가격표: https://www.make.com/en/pricing
