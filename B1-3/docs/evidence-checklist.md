# 실행 증빙 및 캡처 체크리스트

## 프로젝트 1 — n8n

- [x] 전체 워크플로우 구성 화면
- [ ] Webhook 설정 화면(운영 URL은 일부 마스킹)
- [ ] IF 조건 설정 화면
- [x] 긴급 경로 전체가 실행된 화면
- [x] 긴급 JSON 응답 결과 파일
- [x] 일반 경로 전체가 실행된 화면
- [x] 일반 JSON 응답 결과 파일
- [x] Executions의 성공 기록 2건 이상

## 프로젝트 1 — Make

- [x] 전체 시나리오 구성 화면
- [ ] Custom webhook 설정 화면(URL 일부 마스킹)
- [x] Router의 urgent filter가 표시된 구성 화면
- [x] fallback route가 표시된 구성 화면
- [x] 긴급 경로 실행 결과 화면
- [x] 긴급 JSON 응답 결과 파일
- [x] 일반 경로 실행 결과 화면
- [x] 일반 JSON 응답 결과 파일
- [x] Scenario history의 성공 기록 2건

## 프로젝트 2 — n8n

- [x] 전체 워크플로우 구성 화면
- [ ] Schedule Trigger 설정 화면
- [ ] HTTP Request 설정 화면
- [ ] IF 상태 코드 조건 화면
- [x] 정상 경로 실행 화면
- [x] 장애 경로 실행 화면
- [x] Data Table에 정상/장애 행이 함께 저장된 화면
- [x] 게시된 Schedule Trigger 화면

## 보안 점검

- [x] Webhook 운영 URL을 제출 문서와 캡처에서 제외
- [x] 계정 이메일과 사용자명 미노출 확인
- [x] 쿠키, 토큰, API Key, 비밀번호 미노출
- [x] 브라우저 주소창의 민감한 쿼리 문자열 미노출
- [x] 테스트 데이터에 실제 고객 개인정보 미사용

## 권장 파일명

- `p1-n8n-workflow.png`
- `p1-n8n-urgent-result.png`
- `p1-n8n-normal-result.png`
- `p1-make-scenario.png`
- `p1-make-urgent-result.png`
- `p1-make-normal-result.png`
- `p2-n8n-workflow.png`
- `p2-n8n-success-result.png`
- `p2-n8n-failure-result.png`
- `p2-n8n-data-table.png`
