# 스토리보드 — 앱스피아(Appspia) 10초 브랜드 광고

> 브랜드 아이덴티티: [01_brand_identity.md](01_brand_identity.md) 참고
> 최종 영상: 10초 이내 / 16:9 / 1080p / 24~30fps / H.264+AAC

## 0. 사용 도구 목록 (주 도구 + 대체 도구)

| 역할 | 주 도구 | 선택 이유 | 대체 도구 |
|---|---|---|---|
| 이미지 생성 | 나노바나나 2.0 (Gemini) | 씬별 키비주얼 생성. 레퍼런스 이미지 기반 멀티턴 수정이 가능해 씬 간 스타일 일관성 유지에 유리 | Midjourney |
| 비디오 변환 | Google Flow (Veo 3.1) | 이미지→비디오 변환 + 시네마틱 실사 질감. 네이티브 오디오 동시 생성 | Kling, Pika |
| 오디오 (BGM·효과음) | Flow(Veo) 네이티브 오디오 | 영상 생성 시 장면에 맞는 앰비언트/효과음이 함께 생성되어 화면-소리 싱크가 자연스러움 | Suno |
| 오디오 (내레이션) | Gemini TTS (Google AI Studio) | 한국어 내레이션 품질·목소리 제어가 필요. Veo는 한국어 음성 미지원·목소리 지정 불가 리스크가 있어 분리 | ElevenLabs, 타 TTS |

## 1. 전체 구조 (기승전결, 총 10초)

| 씬 | 구간 | 역할 | 한 줄 요약 |
|---|---|---|---|
| 1 | 0~3초 | 문제 제시 (기) | AI 시대의 변화 앞에 막막한 사무실 |
| 2 | 3~7초 | 전환 (승·전) | 강의를 통해 팀과 업무가 움직이기 시작 |
| 3 | 7~10초 | 해결/각인 (결) | 브랜드 로고 + 슬로건 + CTA |

- 마지막 3초(씬 3)에 브랜드 인지 장치(로고+슬로건+CTA) 배치 → 과제 필수 요건 충족
- 내레이션(Gemini TTS, 남성 차분한 톤 1명으로 통일):
  - 씬1: "AI 시대, 어디서부터 시작해야 할까요?"
  - 씬2: "25년의 현장 경험이, 실무의 답을 드립니다."
  - 씬3: "AI 전환, 현장을 아는 사람에게. 앱스피아."

## 2. 스타일 일관성 전략

- **공통 스타일 접두어**(모든 이미지/비디오 프롬프트 앞에 고정):
  `cinematic photorealistic, deep navy and electric blue color grade, soft volumetric lighting, shallow depth of field, 16:9 —` 
- 씬 1 키비주얼을 먼저 확정한 뒤, **나노바나나의 레퍼런스 이미지(멀티턴) 기능으로 씬 2·3의 색감/조명을 씬 1에 고정**
- 인물은 실존 인물 대체가 아닌 **가상의 직장인/강사, 실루엣·뒷모습·손 중심** (딥페이크 제약 준수)
- 로고/한글 텍스트는 생성 이미지에 포함하지 않고 **6단계 편집에서 자막·타이틀로 삽입** (AI 텍스트 오탈자 방지)

## 3. 파일명 규칙

`scene{번호}_{용도}.{확장자}` — 예: `scene01_keyvisual.png`, `scene01_motion.mp4`, `narration_full.mp3`, 최종본 `appspia_ad_final.mp4`

---

## 씬 1 — 문제 제시 (기)

| 필드 | 내용 |
|---|---|
| 씬 번호 / 길이 | Scene 1 / 3초 |
| 목표 메시지 | "AI 시대의 변화 속도 앞에 실무자는 막막하다" — 타겟의 문제를 첫 컷에 공감시킨다 |
| 화면 구성 | 늦은 밤 사무실, 창밖 도시 야경 / 모니터 여러 대에 쏟아지는 알림·차트 / 뒷모습의 직장인 1명(실루엣) / 화면 내 텍스트 없음 |
| 내레이션 | "AI 시대, 어디서부터 시작해야 할까요?" |
| 사용 도구·목적 | 나노바나나(키비주얼) → Flow(모션: 느린 줌인 + 모니터 빛 깜빡임, 오디오: 낮은 앰비언트·키보드 소리) → Gemini TTS(내레이션) |
| 입력 프롬프트 (이미지) | `cinematic photorealistic, deep navy and electric blue color grade, soft volumetric lighting, shallow depth of field, 16:9 — a lone office worker seen from behind as a dark silhouette, facing multiple glowing monitors overflowing with charts and notification popups, late night office, city lights through the window, sense of overwhelm, no text` |
| 입력 프롬프트 (비디오) | `slow push-in toward the silhouetted worker, monitors flickering with data, subtle screen glow pulsing. Audio: low tense ambient hum, faint keyboard typing, distant city noise. No dialogue.` |
| 출력 결과 요약 | (수정 후 최종본) 뒷모습 실루엣 + 네트워크 그래프/코드/와이어프레임 등 AI 대시보드 화면, 딥네이비-일렉트릭 블루 모노톤 확보. 승인 완료 |
| 결과 파일명 | scene01_keyvisual.png / scene01_motion.mp4 |

## 씬 2 — 전환 (승·전)

| 필드 | 내용 |
|---|---|
| 씬 번호 / 길이 | Scene 2 / 4초 |
| 목표 메시지 | "현장을 아는 강사의 교육으로 팀과 업무가 실제로 움직이기 시작한다" |
| 화면 구성 | 밝은 강의장/세미나룸 / 대형 스크린 앞 강사(뒷모습 또는 옆모습 실루엣, 손 제스처 강조) / 수강생들의 노트북 화면이 정돈되어 작동 / 화면 내 텍스트 없음 |
| 내레이션 | "25년의 현장 경험이, 실무의 답을 드립니다." |
| 사용 도구·목적 | 나노바나나(씬1 레퍼런스 고정으로 톤 유지) → Flow(모션: 강사 제스처 + 수강생 화면 패닝, 오디오: 밝아지는 앰비언트·마커/키보드 소리) → Gemini TTS |
| 입력 프롬프트 (이미지, 수정 후 최종) | `cinematic photorealistic, deep navy and electric blue monochrome color grade only, no orange or red tones, soft volumetric lighting, shallow depth of field, 16:9 — a confident female instructor in silhouette gesturing toward a large bright presentation screen filled with AI dashboards, world data maps and visualizations, in a modern seminar room, a diverse group of Korean and Asian professionals seated at laptops in soft silhouette and backlit with minimal facial detail, organized dashboards glowing on their screens, atmosphere shifting from dark to bright blue, sense of clarity and momentum, no text, no readable logos` |
| 입력 프롬프트 (비디오) | `smooth lateral pan across the seminar room, instructor gesturing at the glowing screen, students' laptop screens lighting up one by one. Audio: uplifting subtle tech ambient rising in energy, soft marker and keyboard sounds. No dialogue.` |
| 출력 결과 요약 | 서울 스카이라인 배경 + 동양인 청중으로 현지성 확보, 씬1과 색감 통일. 화면 속 "AI/Data Dashboard" 짧은 영어 텍스트가 일부 보이나 브랜드 텍스트 아니므로 허용. 승인 완료 |
| 결과 파일명 | scene02_keyvisual.png / scene02_motion.mp4 |

## 씬 3 — 해결/브랜드 각인 (결)

| 필드 | 내용 |
|---|---|
| 씬 번호 / 길이 | Scene 3 / 3초 |
| 목표 메시지 | "AX 교육 = 앱스피아" 각인 + 교육 문의 유도 (브랜드 인지 장치: 로고+슬로건+CTA) |
| 화면 구성 | 딥네이비 추상 배경(푸른 빛 파티클·데이터 라인이 모여드는 모션) / 중앙에 실제 로고 [appspia_logo_final.png](appspia_logo_final.png)(워드마크, 모노톤 블루, 편집 삽입) / 하단 슬로건+CTA 자막(편집 삽입) |
| 내레이션 / 카피 | 내레이션: "AI 전환, 현장을 아는 사람에게. 앱스피아." / 화면 카피: "AI 전환, 현장을 아는 사람에게 배우세요." + "교육 문의 · Appspia" |
| 사용 도구·목적 | 나노바나나(추상 배경 키비주얼) → Flow(모션: 파티클이 중앙으로 수렴, 오디오: 정리되는 느낌의 사운드 로고풍 마무리) → Gemini TTS / 로고·자막은 편집(ffmpeg) 삽입 |
| 입력 프롬프트 (이미지) | `cinematic, deep navy background with elegant electric blue light particles and thin data lines converging toward the bright center, premium tech brand aesthetic, clean minimal composition, empty center space reserved for a logo, 16:9, no text, no faces, no people` |
| 입력 프롬프트 (비디오) | `blue light particles and data lines flow smoothly toward the center and settle into a calm glowing focal point. Audio: refined tech ambient resolving into a single warm confident tone, like an audio logo. No dialogue.` |
| 출력 결과 요약 | 중앙에 자연스러운 어두운 원형 여백이 생겨 로고 배치에 최적. [appspia_logo_final.png](appspia_logo_final.png) 합성 테스트 완료 — 대비·톤 모두 양호. 승인 완료 |
| 결과 파일명 | scene03_keyvisual.png / scene03_motion.mp4 (편집 시 appspia_logo_final.png 오버레이) |

---

## 4. 프롬프트 수정 전/후 기록 (과제 필수 — 최소 1개 씬)

> 3단계(이미지 생성)에서 실제 수정이 발생한 씬에 기록한다.

### 씬 1 프롬프트 개선 로그

- **수정 전 프롬프트:** `cinematic photorealistic, deep navy and electric blue color grade, soft volumetric lighting, shallow depth of field, 16:9 — a lone office worker seen from behind as a dark silhouette, facing multiple glowing monitors overflowing with charts and notification popups, late night office, city lights through the window, sense of overwhelm, no text`
- **문제:** 결과물의 모니터 차트에 브랜드 팔레트에 없는 **주황/앰버 색상**이 강하게 섞여 나왔고, 화면 구성이 **주식 트레이딩 데스크**처럼 보여 "AI 전환 앞의 막막한 실무자"라는 메시지보다 금융 종사자 인상이 강했음
- **수정 후 프롬프트:** `cinematic photorealistic, deep navy and electric blue monochrome color grade only, no orange or red tones, soft volumetric lighting, shallow depth of field, 16:9 — a lone office worker seen from behind as a dark silhouette, facing multiple glowing monitors filled with abstract AI dashboards, code snippets, notification alerts and data charts (no finance/trading terminology), late night office, city lights through the window, sense of being overwhelmed by rapid technological change, no text`
- **변경 포인트:** ① "monochrome ... no orange or red tones"로 색상 강하게 제약 ② "trading/finance" 대신 "AI dashboards, code snippets"로 화면 내용 구체화
- **결과 변화:** 주황색이 완전히 사라지고 딥네이비-일렉트릭 블루 모노톤으로 통일, 화면 콘텐츠가 네트워크 그래프·코드·와이어프레임 등 일반 AI/데이터 대시보드로 바뀌어 메시지 적합성 개선 → **승인**

### 씬 2 프롬프트 개선 로그

- **수정 전 프롬프트:** `... engaged professionals at laptops with clean organized dashboards ... no text, no recognizable faces`
- **문제:** 청중 전원이 서구권 외국인 얼굴로 생성되어, 국내 기업 대상 브랜드(앱스피아)의 타겟 현지성과 맞지 않음
- **수정 후 프롬프트:** `a diverse group of Korean and Asian professionals seated at laptops in soft silhouette and backlit with minimal facial detail ...`
- **변경 포인트:** 청중을 한국인/동양인으로 명시, 얼굴 디테일을 최소화하는 조명 조건(backlit) 추가로 씬1과의 실루엣 통일성도 함께 보완
- **결과 변화:** 청중이 동양인으로 바뀌었고 창밖에 서울 스카이라인이 추가로 반영되어 국내 타겟 현지성이 강화됨 → **승인**

## 4-1. 4단계 비디오 변환 결과 (Google Flow / Veo)

| 씬 | 결과 |
|---|---|
| 씬1 | scene01_motion.mp4 — 4.01초/720p/24fps/H.264+AAC, 오디오 mean -31.9dB(낮고 긴장감). 승인 |
| 씬2 | scene02_motion.mp4 — 4.01초/720p/24fps/H.264+AAC, 오디오 mean -24.2dB(상승하는 에너지). 승인 |
| 씬3 | scene03_motion.mp4 — 4.01초/720p/24fps/H.264+AAC, 오디오 mean -20.3dB(확신에 찬 톤). 최초 생성 시 로고("Appspia" 텍스트)가 클립 전체(0~4초)에 노출되어, 로고 없는 원본 키비주얼로 재생성 → 승인 |

- **로고 삽입 방식 결정:** Google Flow의 "Ingredients to Video" 기능으로 로고 이미지를 함께 넣어 네이티브 리빌 생성도 가능함을 확인했으나, 씬3이 편집 후 3초로 매우 짧아 정확한 타이밍 제어가 어렵고 재시도 크레딧 소모 우려가 있어 **기각**. 로고는 계획대로 6단계 ffmpeg 편집에서 [appspia_logo_final.png](appspia_logo_final.png)를 정밀하게 오버레이하는 방식으로 확정
- 전체 영상 스펙: 최종 길이 10초 목표 대비 3개 클립 합 12.03초 → 편집 단계에서 씬1·3을 각 3초로, 씬2를 4초로 트리밍 필요
- 해상도 720p는 과제 "저사양 허용" 기준(720p 이상) 충족, 1080p 필수 아님

## 5-1. 보너스 3 — 플랫폼별 화면비(9:16 인스타그램) 확장 전략

- **진행 시점:** 16:9 기본 10초 영상 완성 후, 보너스 작업으로 별도 진행 (프롬프트 수정 이력 혼선 방지)
- **재사용 방식:** 공통 스타일 접두어와 장면 묘사(피사체/조명/움직임) 프롬프트는 그대로 재사용하고, 화면비 지정만 `16:9` → `9:16`으로 교체. 단, 세로 구도에 맞춰 화면 구성 문구(인물 배치 등)를 소폭 조정
  - 근거: 나노바나나 2.0은 1:1/4:5/9:16/16:9 등 다양한 비율을 프롬프트 지정으로 지원, Google Flow(Veo 3.1, 2026-01 업데이트)는 9:16을 단순 크롭이 아닌 네이티브 세로 구도로 지원
- **내레이션(Gemini TTS):** 화면비와 무관하므로 그대로 재사용, 편집 단계에서 세로 버전 자막 위치만 재배치
- **크레딧 영향:** 씬 3개 × 이미지·비디오 재생성으로 약 2배 소모 예상
- **파일명:** `scene0{n}_keyvisual_916.png`, `scene0{n}_motion_916.mp4`, 최종본 `appspia_ad_final_916.mp4`
- **저장 위치:** `916/` 서브폴더에 관련 파일 전체 보관

## 5-2. 보너스 3 실행 결과

- **이미지 재생성:** 씬1~3 프롬프트를 재사용하고 화면비만 9:16으로 교체, 세로 구도에 맞게 화면 구성 문구만 소폭 조정(예: 씬1 모니터 스택을 세로로, 씬2 청중을 앞뒤 깊이감으로 배치). 3장 모두 1536×2752(9:16) 생성, 16:9 버전에서 겪었던 주황색/트레이딩 느낌 문제 없이 첫 시도에 통과
- **비디오 변환 이슈:** 씬2 비디오 생성 시 Flow에서 "유해 콘텐츠 정책 위반 가능성" 오류 발생 — 원인은 여러 인물의 얼굴이 보이는 장면을 애니메이션화하는 데 대한 정책으로 추정. 프롬프트에서 "instructor gesturing", "students' screens lighting up one by one" 등 **개별 인물 동작 묘사를 제거**하고 카메라·환경 중심 모션으로 전환("calm and mostly still" 인물 묘사)하여 재시도 후 정상 생성
- **비디오 결과:** 3개 클립 모두 4.01초 / 720×1280(9:16) / 24fps / H.264+AAC, 오디오 mean -34.5→-31.7→-25.6dB로 16:9와 동일한 상승 아크 유지
- **워터마크 처리:** 새 해상도(720×1280)에서 좌표 재측정 후 delogo 적용. 16:9와 달리 이번엔 delogo의 십자형 잔상이 전 구간(씬1~3)에 걸쳐 남아, 시간 제한 없이 **영상 전체에 부드러운 원형 비네트(다크 패치)를 상시 오버레이**하여 자연스러운 모서리 그림자로 처리
- **오디오:** 신규 생성 없이 기존 `narration_full_trimmed.wav` 재사용
- **브랜드 카드 재설계:** 좁아진 가로 폭(720px)에 맞춰 슬로건을 2줄로 줄바꿈, 폰트 크기 자동 축소 로직(fit_font)으로 텍스트 폭 초과 방지. 로고는 씬3 영상 실제 오브 중심(약 360,615)에 맞춰 배치
- **최종 파일:** [916/appspia_ad_final_916.mp4](916/appspia_ad_final_916.mp4) — 10.00초 / 720×1280(9:16) / 24fps / H.264+AAC, 승인 완료

## 4-2. 5단계 오디오(내레이션) 결과

- 도구: Gemini TTS — 3문장 단일 화자 통으로 생성 → `narration_full.wav`
- **문제:** 원본 11.44초로 최종 영상 목표(10초 이내) 초과 (문장 내 쉼표마다 TTS가 자연스러운 pause를 삽입한 결과)
- **조치:** 목소리 속도/피치는 그대로 유지, 문장 사이 pause 5곳을 0.4~0.6초 → 0.15초로 트리밍(ffmpeg 세그먼트 재조합) → `narration_full_trimmed.wav`, **9.51초**로 목표 충족
- 음량: mean -16.2dB / max -2.1dB, 클리핑 없음 — 최종 사용 파일

## 4-3. 6단계 ffmpeg 통합 편집 결과

- **최종 파일:** [appspia_ad_final.mp4](appspia_ad_final.mp4) — 10.00초 / 1280×720(720p) / 24fps / H.264 / AAC
- **구성:** 씬1(0~3초, 트리밍) + 씬2(3~7초) + 씬3(7~10초, 트리밍) 영상 연결, 씬별 Veo 앰비언트 오디오를 볼륨 35%로 낮춰 배경에 깔고 그 위에 `narration_full_trimmed.wav` 내레이션 믹스
- **브랜드 각인 장치(마지막 3초, 과제 필수 요건):** [brand_card.png](brand_card.png)(로고 + "AI 전환, 현장을 아는 사람에게 배우세요." + "교육 문의 · www.appspia.kr/educator") 를 7~10초 구간에 0.4초 페이드인으로 오버레이
- **제작 이슈 및 해결:** 최초 시도에서 ffmpeg `drawtext` 필터(한글 폰트 처리, fontconfig 스캔 추정)와 대형 단일 filter_complex 조합이 원인 불명의 폭주(출력 길이가 10초 대신 4시간+ 로 렌더링)를 일으켜 작업을 중단. 원인 격리를 위해 파이프라인을 4단계(①영상 트림·병합 ②오디오 믹스 ③Pillow로 로고+자막 합성한 정적 카드 오버레이 ④최종 먹싱)로 쪼개고, 각 단계에 `-t 10` 안전장치를 명시해 재시도 → 정상 완료
- 텍스트 렌더링은 ffmpeg drawtext 대신 **Pillow(맑은 고딕 Bold)로 사전 합성**하는 방식으로 대체해 한글 자막 안정성 확보

## 4-4. 최종 폴리싱 (사용자 피드백 반영)

- **문제1 — 우하단 생성 워터마크:** Google Flow(Veo)가 생성한 모든 클립 우하단에 작은 반짝이 아이콘이 노출됨
  - 조치: ffmpeg `delogo` 필터로 제거(주변 픽셀 보간). 씬1·2는 완전 제거, 씬3(파티클 선이 교차하는 구간)에는 미세한 격자 잔상이 남아 부드러운 비네트(어둡게 가라앉히는 반투명 패치)로 눈에 띄지 않게 처리
- **문제2 — 로고 위치/가독성:** 로고가 빛나는 구슬 위쪽에 걸쳐 있어 부자연스러움
  - 조치: `brand_card.png` 재구성 — 로고를 구슬 중심으로 이동, 로고 뒤에 딥네이비 톤의 은은한 원형 백플레이트(페더 처리)를 깔아 밝은 배경 위에서도 또렷하게 보이도록 대비 확보. 기존 네이비-블루 팔레트 안에서만 조정해 색상 조화 유지
- 최종 파일: [appspia_ad_final.mp4](appspia_ad_final.mp4) (10.00초, 재검수 완료)

## 5. 오디오 톤 미스매치 대응 (과제 언급 문제에 대한 전략)

- 씬별 Veo 클립의 배경음 톤이 제각각일 수 있음 → 편집 단계에서 Veo 앰비언트는 볼륨을 낮춰 효과음 레이어로 쓰고, **내레이션(Gemini TTS 단일 화자) + 전체 톤을 잡는 오디오 믹스**로 통일
- 내레이션은 한 번에 전체 스크립트를 생성(`narration_full.mp3`)해 목소리 일관성 확보 후, 편집에서 씬별 타이밍에 배치
