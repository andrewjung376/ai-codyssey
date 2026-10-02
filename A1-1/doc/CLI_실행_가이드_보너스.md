# CLI 실행 가이드 (보너스 포함): 중복 검사·영속화·내보내기·수정/삭제·조회수

> 근거 문서: [project.md](../project.md) §5 보너스 과제, [prd.md](prd.md), 기본 가이드 [CLI_실행_가이드.md](CLI_실행_가이드.md)
>
> 이 문서는 기본 가이드의 **1~6장(커밋 #1~#13, `pull` 실습까지)을 마친 뒤 이어서** 진행하는 확장 가이드다. 필수 기능 보완, 리뷰 피드백 4건, **보너스 1·2 전체**를 `prompt-manager` 저장소에 커밋 #14~#26으로 구현한다.
>
> - 코드 조각은 모두 실제 실행으로 검증했다. 각 단계의 **찾을 코드 → 바꿀 코드** 를 VSCode에서 그대로 적용한다.
> - 명령은 **Bash**(Git Bash)와 **Windows 11 cmd** 를 모두 제공한다. 둘 중 하나만 골라 끝까지 사용한다. `git`, `python` 명령은 **공통** 블록으로 한 번만 적었다.
> - 모든 작업은 `C:\dev\git\andrewjung376\prompt-manager` 에서 한다. (`ai-codyssey` 저장소 **밖**)

## 0. 이 문서의 범위

### 보너스 요구사항과 구현

| 보너스 | project.md 요구 | 구현 | 커밋 |
|---|---|---|---|
| 1 | 프롬프트 데이터를 JSON 파일로 저장·불러오기 | 변경 즉시 자동 저장, 시작 시 자동 불러오기, 손상 파일 복구 | #17 |
| 1 | 전체 프롬프트를 카테고리별 Markdown 파일로 내보내기 | 메뉴 8 | #18 |
| 2 | 프롬프트 수정·삭제 | 메뉴 9(수정), 10(삭제) | #20, #21 |
| 2 | 상세 보기 시 조회수 기록 | 메뉴 5 실행 시 +1, 파일에 저장 | #22 |
| 2 | 조회수 기준 Top 목록 | 메뉴 11 | #23 |

### 함께 반영한 리뷰 피드백

| 피드백 | 반영 | 커밋 |
|---|---|---|
| 1. 단계별 스크린샷을 README에 삽입 | README "단계별 실행 예제" 절 | #26 |
| 2. 중복 제목 검사·추가 확인 절차 없음 | 제목 중복 검사(#14), 저장 전 y/n 확인(#15). 수정·삭제에도 같은 확인 적용 | #14, #15, #20, #21 |
| 3. 리스트·딕셔너리 선택 이유(장단점) 누락 | README "데이터 구조와 선택 이유" 절 | #25 |
| 4. 영속화 파일 형식·저장 정책 설계 | JSON 채택(CSV와 비교), 저장 정책 표, 구현 | #17, #25 |

### 셸 표기 규칙

| 표기 | 의미 |
|---|---|
| **Bash** | Git Bash에서 실행 |
| **cmd** | Windows 11 명령 프롬프트에서 실행 |
| **공통** | 두 셸에서 똑같이 실행 |

cmd 사용자는 창을 새로 열 때마다 먼저 실행한다. (자세한 이유는 기본 가이드 0장 참고)

```bat
chcp 65001
set PYTHONUTF8=1
```

cmd 입력 자동 전달 규칙: `&` 앞에는 공백을 넣지 않고, 빈 입력은 `echo.` 를 쓴다.

### 진행 요약

| 단계 | 내용 | 브랜치 | 커밋 |
|---|---|---|---|
| 2 | 시작 준비 | main | – |
| 3 | 필수 기능 보완: 중복 검사, 확인 절차, `.gitignore` | main | #14, #15, #16 |
| 4 | 보너스 1: JSON 영속화, Markdown 내보내기, 병합 | `feature/bonus-json` | #17, #18, 병합 #19 |
| 5 | 보너스 2: 수정, 삭제, 조회수, Top, 병합 | `feature/bonus-crud` | #20~#23, 병합 #24 |
| 6 | README 갱신, 스크린샷 삽입 | main | #25, #26 |
| 7 | 수용 기준 T11~T22 검증 | – | – |
| 8 | 제출물 준비 | – | – |

---

## 1. 설계

### 1-1. 메뉴

```text
=== 나만의 프롬프트 관리 ===
1. 프롬프트 추가
2. 프롬프트 목록
3. 카테고리별 조회
4. 프롬프트 검색
5. 프롬프트 상세 보기        ← 조회수 +1
6. 즐겨찾기 관리
7. 즐겨찾기 목록
8. Markdown 내보내기         ← 보너스 1
9. 프롬프트 수정             ← 보너스 2
10. 프롬프트 삭제            ← 보너스 2
11. 조회수 Top 목록          ← 보너스 2
0. 종료
```

### 1-2. 데이터 스키마

메모리의 `list[dict]` 구조를 그대로 JSON으로 저장한다. 프롬프트 1건은 `title`, `content`, `category`, `favorite`, `views` 5개 필드다.

```json
{
  "version": 2,
  "categories": ["텍스트 생성", "이미지 생성", "영상 생성", "페르소나", "자동화", "기타", "코딩"],
  "prompts": [
    {
      "title": "블로그 글 작성 도우미",
      "content": "당신은 10년 경력의 전문 블로거입니다. ...",
      "category": "텍스트 생성",
      "favorite": true,
      "views": 3
    }
  ]
}
```

- `version`: 이후 형식이 바뀔 때를 대비한 값이다. 현재 프로그램은 값을 검사하지 않는다.
- `views` 가 없는 옛 파일(`version` 1)은 `views` 를 0으로 보고 불러온다.
- 직접 입력한 카테고리도 `categories` 에 함께 저장된다.

### 1-3. 저장 정책

| 항목 | 정책 |
|---|---|
| 파일 형식 | JSON (UTF-8, 들여쓰기 2칸, 한글 그대로 저장) |
| 기본 경로 | `data/prompts.json` (프로그램 파일이 있는 폴더 기준). `--data <경로>` 로 변경 |
| 시작 | 파일이 없으면 기본 프롬프트 5개로 시작한다. 파일은 **첫 변경 때** 만들어진다 (시작만 해서는 생성되지 않음) |
| 저장 시점 | 추가(확인 후), 즐겨찾기 변경, 수정, 삭제, 상세 보기(조회수) 직후 자동 저장. 종료할 때 따로 저장하지 않는다 |
| 저장 방식 | `.tmp` 파일에 먼저 쓰고 `os.replace` 로 교체한다. 쓰는 도중 중단돼도 기존 파일이 남는다 |
| 손상된 파일 | `.bak` 으로 이름을 바꾸고 기본 데이터로 시작하며 안내한다. `.bak` 은 1개만 유지한다(덮어씀) |
| 잘못된 항목 | 필수 값 없음, 타입 오류, 제목 중복 항목은 건너뛰고 건수를 안내한다 |
| 저장 실패 | 경고만 출력하고 이번 실행은 메모리 데이터로 계속한다 |
| 버전 관리 | `data/`, `exports/`, `*.bak`, `*.tmp` 는 `.gitignore` 로 제외한다 (개인 데이터) |
| 초기화 | 저장 파일을 삭제하면 기본 데이터로 돌아간다 |
| 동시 실행 | 지원하지 않는다. 두 프로세스가 쓰면 마지막 저장이 남는다 |

### 1-4. Markdown 내보내기 규칙

- 프롬프트가 1개 이상 있는 **카테고리마다 파일 1개**를 `exports/<카테고리>.md` 에 만든다. `--export-dir <폴더>` 로 위치를 바꾼다.
- 파일 이름에 쓸 수 없는 문자(`\ / : * ? " < > |`)는 `_` 로 바꾼다. 바꾼 결과가 겹치면 `_` 를 덧붙인다.
- 같은 이름의 파일은 덮어쓴다. 프롬프트가 없는 카테고리는 파일을 만들지 않는다.
- 파일 형식: 제목(`#` 카테고리), 개수와 날짜, 프롬프트마다 `##` 제목(즐겨찾기는 ⭐), 번호·조회수, 내용(인용 `>`)

### 1-5. 수정·삭제·조회수 규칙

| 기능 | 규칙 |
|---|---|
| 수정 | 번호 선택 → 새 제목·새 내용(Enter 는 유지) → 카테고리 변경 여부(y/n) → 변경 내용 요약 → `이대로 수정할까요? (y/n)`. 새 제목이 **다른 항목**과 중복이면 다시 입력받는다 (자기 자신은 허용). 바뀐 것이 없으면 저장하지 않는다 |
| 삭제 | 번호 선택 → 대상 표시 → `정말 삭제할까요? (y/n)` → 삭제. 이후 번호가 1씩 당겨진다. 카테고리 목록은 그대로 둔다 |
| 조회수 | 상세 보기(메뉴 5)가 성공할 때마다 +1 하고 저장한다. 잘못된 번호는 올리지 않는다 |
| Top 목록 | 조회수가 1 이상인 항목을 내림차순으로 최대 5개 표시한다. 조회수가 같으면 목록 번호가 빠른 항목이 먼저다 |

### 1-6. 필수 요구사항과의 관계

project.md 필수 항목의 "(종료 시 초기화)"는 영속화가 없는 기본 상태를 설명한 것이다. 이 문서는 보너스 1에 따라 **저장을 기본으로 켠다.** 여전히 "실행 중 추가한 프롬프트와 즐겨찾기 상태가 유지된다"는 필수 요건을 충족하며, 종료 시 초기화가 필요하면 저장 파일을 지우면 된다.

---

## 2. 시작 준비

**Bash**

```bash
cd /c/dev/git/andrewjung376/prompt-manager
```

**cmd**

```bat
cd /d C:\dev\git\andrewjung376\prompt-manager
```

**공통**

```bash
git checkout main
git pull
git status
git log --oneline -3
```

`nothing to commit, working tree clean` 이 보이고, 기본 가이드의 마지막 커밋(`Update README.md` 또는 `docs: 제출용 스크린샷 추가`)이 맨 위에 있으면 시작할 수 있다.

---

## 3. 필수 기능 보완 (main 브랜치)

### 커밋 #14 — 제목 중복 검사 (피드백 2)

**동작**

- 제목 비교는 앞뒤 공백을 지우고, 연속 공백을 한 칸으로 줄이고, 대소문자를 구분하지 않는다. (`Test A` 와 `TEST   a` 는 같은 제목)
- 중복이면 기존 항목을 보여 주고 `다른 제목을 입력할까요? (y/n)` 를 묻는다. `y` 는 재입력, `n` 은 추가 취소다.

**1) 새 함수 추가** — `def main():` 바로 위에 붙여넣는다.

```python
def normalize_title(title):
    return " ".join(title.split()).casefold()


def find_duplicate(title, exclude=None):
    key = normalize_title(title)
    for number, prompt in enumerate(prompts, 1):
        if number != exclude and normalize_title(prompt["title"]) == key:
            return number
    return None


def confirm(message):
    while True:
        answer = input(f"{message} (y/n): ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("y 또는 n 으로 입력하세요.")


def input_unique_title():
    while True:
        title = input_non_empty("제목: ")
        number = find_duplicate(title)
        if number is None:
            return title
        existing = format_prompt_line(number, prompts[number - 1])
        print(f"이미 같은 제목의 프롬프트가 있습니다: {existing}")
        if not confirm("다른 제목을 입력할까요?"):
            return None
```

**2) `add_prompt()` 의 제목 입력 부분 교체**

**찾을 코드**

```python
    print("\n=== 프롬프트 추가 ===")
    title = input_non_empty("제목: ")
```

**바꿀 코드**

```python
    print("\n=== 프롬프트 추가 ===")
    title = input_unique_title()
    if title is None:
        print("추가를 취소했습니다.")
        return
```

**실행 확인**

**Bash**

```bash
printf '1\n블로그 글 작성 도우미\nn\n2\n0\n' | python prompt_manager.py
```

**cmd**

```bat
(echo 1& echo 블로그 글 작성 도우미& echo n& echo 2& echo 0) | python prompt_manager.py
```

`이미 같은 제목의 프롬프트가 있습니다: 1. [텍스트 생성] 블로그 글 작성 도우미 ⭐` 와 `추가를 취소했습니다.` 가 출력되고, 목록은 `총 5개의 프롬프트` 여야 한다.

**커밋**

**공통**

```bash
git add prompt_manager.py
git commit -m "feat: 프롬프트 추가 시 제목 중복 검사"
git push
```

### 커밋 #15 — 추가 전 확인 절차 (피드백 2)

**동작**

- 카테고리까지 입력하면 제목·카테고리·내용(60자까지)을 보여 주고 `이대로 추가할까요? (y/n)` 를 묻는다.
- `n` 이면 `추가를 취소했습니다.` 를 출력하고 아무것도 저장하지 않는다. `y`, `n` 외의 입력은 다시 묻는다.
- 직접 입력한 새 카테고리는 **확인 후에만** 카테고리 목록에 추가한다. (취소해도 빈 카테고리가 남지 않는다)

**1) 새 함수 추가** — `def main():` 바로 위

```python
def shorten(text, limit=60):
    return text if len(text) <= limit else text[:limit] + "…"
```

**2) `select_category()` 의 직접 입력 부분 교체**

**찾을 코드**

```python
    if allow_custom and selected == custom_no:
        name = input_non_empty("새 카테고리 이름: ")
        if name not in categories:
            categories.append(name)
        return name
```

**바꿀 코드**

```python
    if allow_custom and selected == custom_no:
        return input_non_empty("새 카테고리 이름: ")
```

**3) `add_prompt()` 의 저장 부분 교체**

**찾을 코드**

```python
    prompts.append(
        {"title": title, "content": content, "category": category, "favorite": False}
    )
```

**바꿀 코드**

```python
    print("\n--- 입력 내용 확인 ---")
    print(f"제목: {title}")
    print(f"카테고리: {category}")
    print(f"내용: {shorten(content)}")
    if not confirm("이대로 추가할까요?"):
        print("추가를 취소했습니다.")
        return
    if category not in categories:
        categories.append(category)
    prompts.append(
        {"title": title, "content": content, "category": category, "favorite": False}
    )
```

**실행 확인**

**Bash**

```bash
printf '1\n테스트 제목\n테스트 내용\n1\ny\n2\n0\n' | python prompt_manager.py
printf '1\n테스트 제목\n테스트 내용\n1\nn\n2\n0\n' | python prompt_manager.py
```

**cmd**

```bat
(echo 1& echo 테스트 제목& echo 테스트 내용& echo 1& echo y& echo 2& echo 0) | python prompt_manager.py
(echo 1& echo 테스트 제목& echo 테스트 내용& echo 1& echo n& echo 2& echo 0) | python prompt_manager.py
```

첫 번째는 목록 6번에 `[텍스트 생성] 테스트 제목` 이 보이고, 두 번째는 `추가를 취소했습니다.` 후 `총 5개의 프롬프트` 여야 한다. (아직 저장 기능이 없으므로 실행할 때마다 기본 5개로 시작한다)

**커밋**

**공통**

```bash
git add prompt_manager.py
git commit -m "feat: 프롬프트 추가 전 확인 절차"
git push
```

### 커밋 #16 — `.gitignore` 조정 (피드백 4 준비)

저장 파일(`data/`)과 내보내기 결과(`exports/`)는 개인 데이터이므로 저장소에 올리지 않는다. 기존의 `*.json` 은 다른 JSON 파일까지 막으므로 제거하고, 필요한 경로만 명시한다. **영속화를 구현하기 전에** 먼저 적용해 데이터 파일이 실수로 커밋되지 않게 한다.

**Bash**

```bash
cat > .gitignore <<'EOF'
__pycache__/
*.pyc
.venv/
.vscode/
data/
exports/
*.bak
*.tmp
EOF
```

**cmd**

```bat
(echo __pycache__/& echo *.pyc& echo .venv/& echo .vscode/& echo data/& echo exports/& echo *.bak& echo *.tmp) > .gitignore
type .gitignore
```

**확인** — 아직 파일이 없어도 규칙이 적용되는지 확인한다.

**공통**

```bash
git check-ignore -v data/prompts.json exports/example.md data/prompts.json.bak
```

세 경로 모두 `.gitignore` 의 규칙과 함께 출력되면 정상이다.

**커밋**

**공통**

```bash
git add .gitignore
git commit -m "chore: .gitignore를 data/·exports/ 기준으로 조정"
git push
```

---

## 4. 보너스 1 — JSON 영속화와 Markdown 내보내기

기능 단위 브랜치 `feature/bonus-json` 에서 작업하고 `main` 에 병합한다. (`checkout`, `merge`)

**공통**

```bash
git checkout -b feature/bonus-json
git branch
```

### 커밋 #17 — JSON 영속화 (피드백 4)

설계는 1-2, 1-3 의 표를 따른다. 아래 6개 변경을 순서대로 적용한다.

**1) 가져오기(import) 추가** — 파일 맨 위 설명 아래

**찾을 코드**

```python
"""나만의 프롬프트 관리 프로그램 (콘솔 기반)"""
```

**바꿀 코드**

```python
"""나만의 프롬프트 관리 프로그램 (콘솔 기반)"""

import json
import os
import sys
```

**2) 상수 추가** — `prompts = ...` 줄 아래

**찾을 코드**

```python
prompts = [dict(p) for p in DEFAULT_PROMPTS]
```

**바꿀 코드**

```python
prompts = [dict(p) for p in DEFAULT_PROMPTS]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_VERSION = 2
DEFAULT_DATA_FILE = os.path.join(BASE_DIR, "data", "prompts.json")
data_path = DEFAULT_DATA_FILE
```

**3) 새 함수 추가** — `def main():` 바로 위

```python
def get_option(argv, name, default):
    if name in argv:
        index = argv.index(name)
        if index + 1 < len(argv):
            return argv[index + 1]
        print(f"{name} 뒤에 값이 필요합니다. 기본값을 사용합니다.")
    return default


def is_valid_prompt(item):
    if not isinstance(item, dict):
        return False
    for key in ("title", "content", "category"):
        if not isinstance(item.get(key), str) or not item[key].strip():
            return False
    views = item.get("views", 0)
    if isinstance(views, bool) or not isinstance(views, int) or views < 0:
        return False
    return isinstance(item.get("favorite"), bool)


def backup_broken_file(path):
    try:
        os.replace(path, path + ".bak")
    except OSError:
        pass


def load_data(path):
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        raw_prompts = data["prompts"]
        raw_categories = data["categories"]
        if not isinstance(raw_prompts, list) or not isinstance(raw_categories, list):
            raise ValueError("prompts, categories 는 목록이어야 합니다")
    except (OSError, ValueError, KeyError, TypeError) as error:
        backup_broken_file(path)
        print(f"저장 파일을 읽을 수 없어 기본 데이터로 시작합니다. 원본은 .bak 으로 보관했습니다. ({error})")
        return
    loaded = []
    seen = set()
    skipped = 0
    for item in raw_prompts:
        key = normalize_title(item["title"]) if is_valid_prompt(item) else None
        if key is None or key in seen:
            skipped += 1
            continue
        seen.add(key)
        loaded.append(
            {
                "title": item["title"],
                "content": item["content"],
                "category": item["category"],
                "favorite": item["favorite"],
                "views": item.get("views", 0),
            }
        )
    prompts[:] = loaded
    for name in raw_categories + [p["category"] for p in loaded]:
        if isinstance(name, str) and name.strip() and name not in categories:
            categories.append(name)
    if skipped:
        print(f"형식이 잘못되었거나 제목이 중복된 항목 {skipped}개를 건너뛰었습니다.")


def save_data(path):
    data = {"version": SCHEMA_VERSION, "categories": categories, "prompts": prompts}
    tmp_path = path + ".tmp"
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except OSError as error:
        print(f"저장에 실패했습니다. 이번 실행 동안만 유지됩니다. ({error})")
```

**4) `main()` 시작 부분 교체** — 실행 옵션을 읽고 저장 파일을 불러온다

**찾을 코드**

```python
def main():
    try:
```

**바꿀 코드**

```python
def main():
    global data_path
    data_path = get_option(sys.argv, "--data", DEFAULT_DATA_FILE)
    load_data(data_path)
    try:
```

**5) `add_prompt()` 에 저장 추가**

**찾을 코드**

```python
        {"title": title, "content": content, "category": category, "favorite": False}
    )
    print("\n프롬프트가 추가되었습니다!")
```

**바꿀 코드**

```python
        {"title": title, "content": content, "category": category, "favorite": False}
    )
    save_data(data_path)
    print("\n프롬프트가 추가되었습니다!")
```

**6) `toggle_favorite()` 에 저장 추가**

**찾을 코드**

```python
    prompt["favorite"] = not prompt["favorite"]
    state = "추가" if prompt["favorite"] else "해제"
```

**바꿀 코드**

```python
    prompt["favorite"] = not prompt["favorite"]
    save_data(data_path)
    state = "추가" if prompt["favorite"] else "해제"
```

> `views`(조회수)는 #22 에서 추가한다. 그 전에는 `views` 가 없어도 `0` 으로 처리되므로 지금 단계에서도 정상 동작한다.

**실행 확인** — 시험용 파일 `data/demo.json` 을 사용한다.

**Bash**

```bash
mkdir -p data
printf '1\n저장 테스트\n내용\n1\ny\n0\n' | python prompt_manager.py --data data/demo.json
head -n 14 data/demo.json
printf '2\n0\n' | python prompt_manager.py --data data/demo.json
rm -f data/demo.json
```

**cmd**

```bat
if not exist data mkdir data
(echo 1& echo 저장 테스트& echo 내용& echo 1& echo y& echo 0) | python prompt_manager.py --data data\demo.json
type data\demo.json
(echo 2& echo 0) | python prompt_manager.py --data data\demo.json
del data\demo.json
```

- 첫 실행 후 `data/demo.json` 이 생성되고 내용이 JSON(`"version": 2`)이어야 한다.
- 두 번째 실행(종료 후 재실행)의 목록에 `6. [텍스트 생성] 저장 테스트` 가 남아 있어야 한다.
- `git status` 에 `data/` 가 나타나지 않아야 한다. (`.gitignore` 적용 확인)

**커밋**

**공통**

```bash
git status
git add prompt_manager.py
git commit -m "feat: JSON 영속화 (저장·불러오기, 손상 복구)"
git push -u origin feature/bonus-json
```

### 커밋 #18 — 카테고리별 Markdown 내보내기

**1) `import datetime` 추가**

**찾을 코드**

```python
import json
```

**바꿀 코드**

```python
import datetime
import json
```

**2) 상수 추가** — 내보내기 폴더와 파일명 금지 문자

**찾을 코드**

```python
data_path = DEFAULT_DATA_FILE
```

**바꿀 코드**

```python
DEFAULT_EXPORT_DIR = os.path.join(BASE_DIR, "exports")
INVALID_FILENAME_CHARS = '\\/:*?"<>|'
data_path = DEFAULT_DATA_FILE
export_dir = DEFAULT_EXPORT_DIR
```

**3) 새 함수 추가** — `def main():` 바로 위

```python
def safe_filename(name):
    cleaned = "".join("_" if ch in INVALID_FILENAME_CHARS else ch for ch in name)
    return cleaned.strip(" .") or "category"


def build_markdown(category, items):
    lines = [f"# {category}", "", f"프롬프트 {len(items)}개 · 내보낸 날짜 {datetime.date.today()}", ""]
    for number, prompt in items:
        star = " ⭐" if prompt["favorite"] else ""
        lines.append(f"## {prompt['title']}{star}")
        lines.append("")
        lines.append(f"- 번호: {number}")
        lines.append(f"- 조회수: {prompt.get('views', 0)}")
        lines.append("")
        for text_line in prompt["content"].splitlines() or [""]:
            lines.append(f"> {text_line}")
        lines.append("")
    return "\n".join(lines) + "\n"


def export_markdown():
    print("\n=== Markdown 내보내기 ===")
    if not prompts:
        print("내보낼 프롬프트가 없습니다.")
        return
    used = set()
    count = 0
    try:
        os.makedirs(export_dir, exist_ok=True)
        for category in categories:
            items = [(n, p) for n, p in enumerate(prompts, 1) if p["category"] == category]
            if not items:
                continue
            filename = safe_filename(category)
            while filename.casefold() in used:
                filename += "_"
            used.add(filename.casefold())
            path = os.path.join(export_dir, filename + ".md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(build_markdown(category, items))
            print(f"- {path} ({len(items)}개)")
            count += 1
    except OSError as error:
        print(f"내보내기에 실패했습니다. ({error})")
        return
    print(f"\n총 {count}개 파일을 내보냈습니다.")
```

**4) 메뉴에 항목 추가** — `show_menu()` 의 `0. 종료` 위

**찾을 코드**

```python
    print("0. 종료")
```

**바꿀 코드**

```python
    print("8. Markdown 내보내기")
    print("0. 종료")
```

**5) `main()` 의 옵션 읽기 교체** — `--export-dir` 지원

**찾을 코드**

```python
    global data_path
    data_path = get_option(sys.argv, "--data", DEFAULT_DATA_FILE)
```

**바꿀 코드**

```python
    global data_path, export_dir
    data_path = get_option(sys.argv, "--data", DEFAULT_DATA_FILE)
    export_dir = get_option(sys.argv, "--export-dir", DEFAULT_EXPORT_DIR)
```

**6) `main()` 의 분기 추가**

**찾을 코드**

```python
            elif choice == "7":
                show_favorites()
```

**바꿀 코드**

```python
            elif choice == "7":
                show_favorites()
            elif choice == "8":
                export_markdown()
```

**실행 확인** — 특수문자가 들어간 카테고리(`a/b:c`)로 파일 이름 치환도 함께 확인한다.

**Bash**

```bash
printf '1\n제목 A\n내용 첫줄\n7\na/b:c\ny\n8\n0\n' | python prompt_manager.py --data data/demo.json --export-dir data/ex
ls data/ex
cat data/ex/a_b_c.md
rm -rf data/demo.json data/ex
```

**cmd**

```bat
(echo 1& echo 제목 A& echo 내용 첫줄& echo 7& echo a/b:c& echo y& echo 8& echo 0) | python prompt_manager.py --data data\demo.json --export-dir data\ex
dir /b data\ex
type data\ex\a_b_c.md
rmdir /s /q data\ex
del data\demo.json
```

- 카테고리별 파일 6개(`텍스트 생성.md`, `이미지 생성.md`, `영상 생성.md`, `페르소나.md`, `자동화.md`, `a_b_c.md`)가 생기고 `총 6개 파일을 내보냈습니다.` 가 출력되어야 한다.
- `a_b_c.md` 는 `# a/b:c` 제목과 `> 내용 첫줄` 인용문을 포함한다.

**커밋**

**공통**

```bash
git add prompt_manager.py
git commit -m "feat: 카테고리별 Markdown 내보내기"
git push
```

### 커밋 #19 — `main` 으로 병합 (`checkout`, `merge`)

**공통**

```bash
git checkout main
git merge --no-ff feature/bonus-json -m "Merge branch 'feature/bonus-json'"
git push
git log --oneline --graph -6
```

그래프에 `|\` … `|/` 갈래가 보이면 성공이다. 브랜치 정리(선택):

**공통**

```bash
git branch -d feature/bonus-json
git push origin --delete feature/bonus-json
```

---

## 5. 보너스 2 — 수정·삭제·조회수·Top 목록

기능 단위 브랜치 `feature/bonus-crud` 에서 작업한다.

**공통**

```bash
git checkout -b feature/bonus-crud
git branch
```

### 커밋 #20 — 프롬프트 수정 (피드백 2 확인 절차 포함)

규칙은 1-5 를 따른다. 제목 중복 검사는 #14 에서 만든 `find_duplicate(title, exclude=...)` 의 `exclude` 로 **자기 자신을 제외**한다.

**1) 새 함수 추가** — `def main():` 바로 위

```python
def input_new_title(number, current):
    while True:
        value = input(f"새 제목 (Enter=유지) [{current}]: ").strip()
        if not value:
            return current
        duplicate = find_duplicate(value, exclude=number)
        if duplicate is None:
            return value
        existing = format_prompt_line(duplicate, prompts[duplicate - 1])
        print(f"이미 같은 제목의 프롬프트가 있습니다: {existing}")


def edit_prompt():
    print("\n=== 프롬프트 수정 ===")
    if not prompts:
        print("등록된 프롬프트가 없습니다.")
        return
    number = input_number("수정할 프롬프트 번호: ", 1, len(prompts))
    if number is None:
        return
    prompt = prompts[number - 1]
    print(f"현재: {format_prompt_line(number, prompt)}")
    new_title = input_new_title(number, prompt["title"])
    new_content = input("새 내용 (Enter=유지): ").strip() or prompt["content"]
    new_category = prompt["category"]
    if confirm(f"카테고리를 변경할까요? (현재: {prompt['category']})"):
        new_category = select_category(allow_custom=True)
    changes = []
    if new_title != prompt["title"]:
        changes.append(f"제목: {prompt['title']} -> {new_title}")
    if new_content != prompt["content"]:
        changes.append(f"내용: {shorten(prompt['content'], 30)} -> {shorten(new_content, 30)}")
    if new_category != prompt["category"]:
        changes.append(f"카테고리: {prompt['category']} -> {new_category}")
    if not changes:
        print("변경된 내용이 없습니다.")
        return
    print("\n--- 변경 내용 확인 ---")
    for change in changes:
        print(change)
    if not confirm("이대로 수정할까요?"):
        print("수정을 취소했습니다.")
        return
    prompt.update(title=new_title, content=new_content, category=new_category)
    if new_category not in categories:
        categories.append(new_category)
    save_data(data_path)
    print("\n프롬프트가 수정되었습니다!")
```

**2) 메뉴 항목 추가**

**찾을 코드**

```python
    print("0. 종료")
```

**바꿀 코드**

```python
    print("9. 프롬프트 수정")
    print("0. 종료")
```

**3) `main()` 분기 추가**

**찾을 코드**

```python
            elif choice == "8":
                export_markdown()
```

**바꿀 코드**

```python
            elif choice == "8":
                export_markdown()
            elif choice == "9":
                edit_prompt()
```

**실행 확인**

**Bash**

```bash
printf '9\n2\n새 썸네일\n새 내용입니다\nn\ny\n2\n0\n' | python prompt_manager.py --data data/demo.json
printf '9\n2\n블로그 글 작성 도우미\n\n\nn\n0\n' | python prompt_manager.py --data data/demo.json
rm -f data/demo.json
```

**cmd**

```bat
(echo 9& echo 2& echo 새 썸네일& echo 새 내용입니다& echo n& echo y& echo 2& echo 0) | python prompt_manager.py --data data\demo.json
(echo 9& echo 2& echo 블로그 글 작성 도우미& echo.& echo.& echo n& echo 0) | python prompt_manager.py --data data\demo.json
del data\demo.json
```

- 첫 번째: `제목: 제품 썸네일 생성 -> 새 썸네일` 변경 요약 후 `프롬프트가 수정되었습니다!`, 목록 2번이 `새 썸네일`
- 두 번째: `이미 같은 제목의 프롬프트가 있습니다` 로 다시 입력받다가 Enter 로 유지하면 `변경된 내용이 없습니다.`

**커밋**

**공통**

```bash
git add prompt_manager.py
git commit -m "feat: 프롬프트 수정"
git push -u origin feature/bonus-crud
```

### 커밋 #21 — 프롬프트 삭제

**1) 새 함수 추가** — `def main():` 바로 위

```python
def delete_prompt():
    print("\n=== 프롬프트 삭제 ===")
    if not prompts:
        print("등록된 프롬프트가 없습니다.")
        return
    number = input_number("삭제할 프롬프트 번호: ", 1, len(prompts))
    if number is None:
        return
    prompt = prompts[number - 1]
    print(f"삭제 대상: {format_prompt_line(number, prompt)}")
    if not confirm("정말 삭제할까요? 되돌릴 수 없습니다."):
        print("삭제를 취소했습니다.")
        return
    prompts.pop(number - 1)
    save_data(data_path)
    print(f"'{prompt['title']}' 프롬프트를 삭제했습니다. (이후 번호가 1씩 당겨집니다)")
```

**2) 메뉴 항목 추가**

**찾을 코드**

```python
    print("0. 종료")
```

**바꿀 코드**

```python
    print("10. 프롬프트 삭제")
    print("0. 종료")
```

**3) `main()` 분기 추가**

**찾을 코드**

```python
            elif choice == "9":
                edit_prompt()
```

**바꿀 코드**

```python
            elif choice == "9":
                edit_prompt()
            elif choice == "10":
                delete_prompt()
```

**실행 확인**

**Bash**

```bash
printf '10\n2\ny\n2\n0\n' | python prompt_manager.py --data data/demo.json
rm -f data/demo.json
printf '10\n2\nn\n2\n0\n' | python prompt_manager.py --data data/demo.json
rm -f data/demo.json
```

**cmd**

```bat
(echo 10& echo 2& echo y& echo 2& echo 0) | python prompt_manager.py --data data\demo.json
del data\demo.json
(echo 10& echo 2& echo n& echo 2& echo 0) | python prompt_manager.py --data data\demo.json
del data\demo.json
```

첫 번째는 `삭제했습니다` 후 `총 4개의 프롬프트`, 두 번째는 `삭제를 취소했습니다.` 후 `총 5개의 프롬프트` 여야 한다.

**커밋**

**공통**

```bash
git add prompt_manager.py
git commit -m "feat: 프롬프트 삭제"
git push
```

### 커밋 #22 — 상세 보기 조회수 기록

조회수 필드 `views` 를 모든 프롬프트가 갖도록 세 곳을 바꾼다.

**1) 기본 데이터 복사 시 `views` 0 부여**

**찾을 코드**

```python
prompts = [dict(p) for p in DEFAULT_PROMPTS]
```

**바꿀 코드**

```python
prompts = [dict(p, views=0) for p in DEFAULT_PROMPTS]
```

**2) `add_prompt()` 의 새 프롬프트에 `views` 추가**

**찾을 코드**

```python
    prompts.append(
        {"title": title, "content": content, "category": category, "favorite": False}
    )
```

**바꿀 코드**

```python
    prompts.append(
        {
            "title": title,
            "content": content,
            "category": category,
            "favorite": False,
            "views": 0,
        }
    )
```

**3) `show_detail()` 에서 조회수 증가·저장·표시**

**찾을 코드**

```python
    prompt = prompts[number - 1]
    line = "─" * 28
    print(f"\n{line}")
    print(f"제목: {prompt['title']}")
    print(f"카테고리: {prompt['category']}")
    print(f"즐겨찾기: {'⭐' if prompt['favorite'] else '-'}")
    print(line)
```

**바꿀 코드**

```python
    prompt = prompts[number - 1]
    prompt["views"] += 1
    save_data(data_path)
    line = "─" * 28
    print(f"\n{line}")
    print(f"제목: {prompt['title']}")
    print(f"카테고리: {prompt['category']}")
    print(f"즐겨찾기: {'⭐' if prompt['favorite'] else '-'}")
    print(f"조회수: {prompt['views']}")
    print(line)
```

**실행 확인**

**Bash**

```bash
printf '5\n2\n5\n2\n0\n' | python prompt_manager.py --data data/demo.json
printf '5\n2\n0\n' | python prompt_manager.py --data data/demo.json
rm -f data/demo.json
```

**cmd**

```bat
(echo 5& echo 2& echo 5& echo 2& echo 0) | python prompt_manager.py --data data\demo.json
(echo 5& echo 2& echo 0) | python prompt_manager.py --data data\demo.json
del data\demo.json
```

첫 실행에서 `조회수: 1`, `조회수: 2` 가 차례로 나오고, **재실행한** 두 번째 실행에서는 `조회수: 3` 이 나와야 한다. (파일에 누적 저장)

**커밋**

**공통**

```bash
git add prompt_manager.py
git commit -m "feat: 상세 보기 조회수 기록"
git push
```

### 커밋 #23 — 조회수 Top 목록

**1) 표시 개수 상수 추가**

**찾을 코드**

```python
SCHEMA_VERSION = 2
```

**바꿀 코드**

```python
SCHEMA_VERSION = 2
TOP_COUNT = 5
```

**2) 새 함수 추가** — `def main():` 바로 위

```python
def show_top():
    print("\n=== 조회수 Top 목록 ===")
    ranked = sorted(enumerate(prompts, 1), key=lambda item: item[1]["views"], reverse=True)
    ranked = [(n, p) for n, p in ranked if p["views"] > 0][:TOP_COUNT]
    if not ranked:
        print("아직 조회 기록이 없습니다. 상세 보기를 하면 조회수가 기록됩니다.")
        return
    for rank, (number, prompt) in enumerate(ranked, 1):
        print(f"{rank}위 (번호 {number}) [{prompt['category']}] {prompt['title']} - 조회 {prompt['views']}회")
```

**3) 메뉴 항목 추가**

**찾을 코드**

```python
    print("0. 종료")
```

**바꿀 코드**

```python
    print("11. 조회수 Top 목록")
    print("0. 종료")
```

**4) `main()` 분기 추가**

**찾을 코드**

```python
            elif choice == "10":
                delete_prompt()
```

**바꿀 코드**

```python
            elif choice == "10":
                delete_prompt()
            elif choice == "11":
                show_top()
```

**실행 확인**

**Bash**

```bash
printf '11\n0\n' | python prompt_manager.py --data data/demo.json
printf '5\n2\n5\n2\n5\n1\n11\n0\n' | python prompt_manager.py --data data/demo.json
rm -f data/demo.json
```

**cmd**

```bat
(echo 11& echo 0) | python prompt_manager.py --data data\demo.json
(echo 5& echo 2& echo 5& echo 2& echo 5& echo 1& echo 11& echo 0) | python prompt_manager.py --data data\demo.json
del data\demo.json
```

첫 번째는 `아직 조회 기록이 없습니다.`, 두 번째는 `1위 (번호 2) ... 조회 2회`, `2위 (번호 1) ... 조회 1회` 가 출력되어야 한다.

**커밋**

**공통**

```bash
git add prompt_manager.py
git commit -m "feat: 조회수 Top 목록"
git push
```

### 커밋 #24 — `main` 으로 병합

**공통**

```bash
git checkout main
git merge --no-ff feature/bonus-crud -m "Merge branch 'feature/bonus-crud'"
git push
git log --oneline --graph -12
```

브랜치 정리(선택):

**공통**

```bash
git branch -d feature/bonus-crud
git push origin --delete feature/bonus-crud
```

---

## 6. README 갱신 (피드백 1, 3, 4)

### 커밋 #25 — 기능·데이터 구조 선택 이유·저장 정책 반영 (피드백 3, 4)

`README.md` 전체를 아래 내용으로 교체한다. 기존 README 의 마지막 줄 `문의: ...` 는 아래 "문의" 절에 보존했다.

**공통**

```bash
code README.md
```

````markdown
# 나만의 프롬프트 관리 프로그램

터미널에서 메뉴 번호를 입력해 프롬프트를 **추가·조회·검색·즐겨찾기·수정·삭제**로 관리하는 Python 콘솔 프로그램입니다.
Python 표준 라이브러리(`json`, `os`, `sys`, `datetime`)와 기본 문법(변수, 조건문, 반복문, 함수, 리스트, 딕셔너리)만 사용했고, 외부 패키지는 설치하지 않습니다.

## 실행 환경

- Python 3.10 이상
- 추가 설치 패키지 없음

## 실행 방법

```bash
git clone https://github.com/andrewjung376/prompt-manager.git
cd prompt-manager
python prompt_manager.py
```

실행 옵션:

| 옵션 | 설명 | 기본값 |
|---|---|---|
| `--data 경로` | 프롬프트를 저장하고 불러올 JSON 파일 | `data/prompts.json` |
| `--export-dir 폴더` | Markdown 내보내기 폴더 | `exports/` |

```bash
python prompt_manager.py --data 내파일.json --export-dir 내보내기
```

Windows 명령 프롬프트(cmd)에서 이모지(⭐)나 한글이 깨지면 아래를 먼저 실행한 뒤 다시 실행하세요.

```bat
chcp 65001
set PYTHONUTF8=1
```

## 기능 목록

| 메뉴 | 기능 | 설명 |
|---|---|---|
| 1 | 프롬프트 추가 | 제목, 내용, 카테고리를 입력해 등록. 같은 제목은 거부하고, 저장 전에 y/n 으로 확인 |
| 2 | 프롬프트 목록 | 전체 프롬프트를 번호, 카테고리, 즐겨찾기(⭐)와 함께 출력 |
| 3 | 카테고리별 조회 | 카테고리를 선택해 해당 프롬프트만 출력 |
| 4 | 프롬프트 검색 | 키워드가 제목 또는 내용에 포함된 프롬프트 검색 (대소문자 무시) |
| 5 | 프롬프트 상세 보기 | 제목, 카테고리, 즐겨찾기, 조회수, 내용 전체 출력. 볼 때마다 조회수 +1 |
| 6 | 즐겨찾기 관리 | 번호를 입력해 즐겨찾기 추가/해제 |
| 7 | 즐겨찾기 목록 | 즐겨찾기한 프롬프트만 출력 |
| 8 | Markdown 내보내기 | 카테고리별 `.md` 파일 생성 |
| 9 | 프롬프트 수정 | 제목·내용·카테고리 수정 (변경 내용을 보여 주고 y/n 확인) |
| 10 | 프롬프트 삭제 | 확인(y/n) 후 삭제 |
| 11 | 조회수 Top 목록 | 조회수 높은 순으로 최대 5개 |
| 0 | 종료 | 프로그램 종료 |

- 각 기능 실행 후에는 메뉴로 돌아옵니다.
- 잘못된 입력은 안내 메시지를 출력합니다.
- 조회·검색·즐겨찾기 목록의 번호는 **전체 목록 기준 번호**이므로, 그대로 상세 보기, 즐겨찾기 관리, 수정, 삭제에 입력할 수 있습니다.
- 삭제하면 이후 번호가 1씩 당겨집니다.
- 변경 내용은 즉시 JSON 파일에 저장되어 다음 실행에도 유지됩니다. (아래 "데이터 저장 정책")

## 입력 안전장치

- **제목 중복 검사:** 앞뒤 공백을 지우고, 연속 공백을 한 칸으로 줄이고, 대소문자를 무시하고 비교합니다. 예: `Test A` 와 `TEST   a` 는 같은 제목입니다.
- **중복일 때:** 기존 항목을 보여 주고 `다른 제목을 입력할까요? (y/n)` 를 묻습니다. `y` 는 재입력, `n` 은 취소입니다.
- **추가 전 확인:** 제목·카테고리·내용 요약을 보여 주고 `이대로 추가할까요? (y/n)` 를 묻습니다. `n` 이면 저장하지 않습니다.
- **수정·삭제:** 수정은 변경 내용 요약 후, 삭제는 대상 표시 후 y/n 으로 확인합니다. 수정 중 제목 중복 검사는 자기 자신을 제외합니다.
- 파일에서 불러올 때도 제목이 중복된 항목은 건너뜁니다.

## 프롬프트 카테고리

| 카테고리 | 설명 |
|---|---|
| 텍스트 생성 | 글, 이메일, 요약 등 텍스트를 만드는 프롬프트 |
| 이미지 생성 | 이미지 생성 AI용 키워드와 지시문 |
| 영상 생성 | 영상 스크립트와 장면 구성 프롬프트 |
| 페르소나 | AI에게 역할과 말투를 부여하는 프롬프트 |
| 자동화 | 반복 업무와 워크플로 자동화용 프롬프트 |
| 기타 | 위에 속하지 않는 프롬프트 |
| (직접 입력) | 추가·수정할 때 만든 새 카테고리. 카테고리 목록에 함께 표시되고 저장됩니다 |

## 기본 등록 프롬프트

저장 파일이 없을 때 이전 미션에서 작성한 프롬프트 5개로 시작합니다.

## 프로젝트 구조

```text
prompt-manager/
├── prompt_manager.py   # 프로그램 전체 (기능별 함수로 분리)
├── README.md
├── .gitignore
├── docs/screenshots/   # 단계별 실행 스크린샷
├── data/               # 실행 중 자동 생성되는 저장 파일 (git 제외)
└── exports/            # Markdown 내보내기 결과 (git 제외)
```

## 데이터 구조와 선택 이유

프롬프트 전체는 **리스트**, 프롬프트 1건은 **딕셔너리**로 저장합니다.

```python
prompts = [
    {"title": "제목", "content": "내용", "category": "텍스트 생성", "favorite": False, "views": 0},
]
```

### 리스트(`list`)를 고른 이유

| 장점 | 단점 |
|---|---|
| 입력 순서가 유지되어 목록 번호(인덱스 + 1)로 바로 사용할 수 있습니다 | 제목으로 찾기·중복 검사가 처음부터 순회하는 O(n) 입니다 |
| `append` 로 추가가 간단합니다 | 번호가 위치에 의존해 삭제·정렬 시 번호가 바뀝니다 |
| `for` 와 리스트 컴프리헨션으로 카테고리·검색·즐겨찾기 필터링이 쉽습니다 | 데이터가 매우 많아지면 비효율적입니다 |
| JSON 배열과 1:1 로 대응됩니다 | |

### 딕셔너리(`dict`)를 고른 이유

| 장점 | 단점 |
|---|---|
| `p["title"]` 처럼 이름으로 접근해 가독성이 좋습니다 (튜플은 `p[0]`) | 키 이름을 틀리면 실행 중 `KeyError` 가 납니다 |
| 필드 추가가 쉽습니다 (조회수 `views` 를 나중에 추가) | 필수 필드와 타입을 강제할 수 없습니다 |
| JSON 객체와 1:1 로 대응됩니다 | 필드마다 키 문자열이 반복되어 메모리를 조금 더 씁니다 |

**보완:** 단점은 `is_valid_prompt()` 로 불러올 때 필수 값과 타입을 검증해 줄였습니다.

### 다른 구조와의 비교

| 구조 | 장점 | 단점 | 채택 |
|---|---|---|---|
| 튜플의 리스트 | 가볍고 불변 | 필드 의미가 불명확하고 수정이 불편(즐겨찾기 토글, 조회수 증가) | 아니오 |
| 제목을 키로 쓰는 딕셔너리 | 제목 조회·중복 검사가 O(1) | 번호 순서로 접근하기 어렵고, 제목 수정 시 키를 바꿔야 함 | 아니오 |
| 클래스(`dataclass`) | 타입과 메서드를 묶을 수 있음 | 과제 범위(리스트·딕셔너리)를 넘어섬 | 아니오 |
| 집합(`set`) | 중복 제거 | 순서와 번호가 없고 딕셔너리를 담을 수 없음 | 아니오 |
| SQLite | 질의와 대용량에 강함 | 이 규모에는 과함, 학습 범위를 넘어섬 | 아니오 |
| **리스트 + 딕셔너리** | 번호 목록, 필터링, JSON 저장에 모두 자연스러움 | 위 단점 | **예** |

**한계와 확장:** 프롬프트가 수천 건이 되면 중복 검사를 `{정규화한 제목: 인덱스}` 색인으로 바꿀 수 있습니다. 이 규모(수십~수백 건)에서는 선형 탐색으로 충분합니다.

## 데이터 저장 정책

### 파일 형식: JSON을 선택한 이유

| 항목 | JSON | CSV |
|---|---|---|
| 구조 | 중첩·목록 가능 (`list[dict]` 그대로) | 평면(행/열) |
| 타입 | `true`/`false`, 숫자, 문자열 구분 | 모두 문자열이라 변환 필요 |
| 줄바꿈·쉼표가 든 내용 | 자동 이스케이프 | 따옴표 처리가 필요하고 도구마다 다름 |
| 카테고리 목록 | 같은 파일에 함께 저장 | 별도 파일 필요 |
| 표준 라이브러리 | `json` | `csv` |
| 사람이 읽기 | 가능 | 스프레드시트에서 편함 |

프롬프트 내용에 줄바꿈이 들어갈 수 있고 `favorite`, `views` 의 타입을 유지해야 해서 JSON 을 선택했습니다. 스프레드시트용 출력이 필요하면 CSV 내보내기를 추가할 수 있습니다.

### 저장 정책

| 항목 | 정책 |
|---|---|
| 파일 | `data/prompts.json` (UTF-8, 들여쓰기 2칸). `--data` 로 변경 |
| 스키마 | `version`, `categories`, `prompts`(`title`, `content`, `category`, `favorite`, `views`). `views` 가 없는 옛 파일은 0으로 처리 |
| 시작 | 파일이 없으면 기본 프롬프트 5개로 시작. 파일은 첫 변경 때 생성 |
| 저장 시점 | 추가, 즐겨찾기, 수정, 삭제, 상세 보기(조회수) 직후 자동 저장 |
| 저장 방식 | `.tmp` 에 먼저 쓰고 `os.replace` 로 교체 (쓰는 도중 중단돼도 기존 파일 유지) |
| 손상된 파일 | `.bak` 으로 이름을 바꾸고 기본 데이터로 시작, 안내 출력 (`.bak` 은 1개만 유지) |
| 잘못된 항목 | 필수 값 없음, 타입 오류, 제목 중복은 건너뛰고 건수 안내 |
| 저장 실패 | 경고만 출력하고 이번 실행은 메모리로 계속 |
| 버전 관리 | `data/`, `exports/`, `*.bak`, `*.tmp` 는 `.gitignore` 로 제외 (개인 데이터) |
| 동시 실행 | 지원하지 않음 (마지막 저장이 남음) |

기본 데이터로 되돌리려면 저장 파일을 삭제합니다.

```bash
rm -f data/prompts.json
```

```bat
del data\prompts.json
```

## Markdown 내보내기

메뉴 8 을 선택하면 프롬프트가 있는 카테고리마다 `exports/<카테고리>.md` 를 만듭니다.

- 파일 이름에 쓸 수 없는 문자(`\ / : * ? " < > |`)는 `_` 로 바뀝니다. 같은 이름이 겹치면 `_` 를 덧붙입니다.
- 같은 이름의 파일은 덮어씁니다.
- 각 파일은 카테고리 제목, 개수와 날짜, 프롬프트별 제목(즐겨찾기는 ⭐)·번호·조회수·내용(인용)으로 구성됩니다.

## 문의

문의: GitHub Issues 를 이용해 주세요.
````

**공통**

```bash
git add README.md
git commit -m "docs: README 보너스 기능·데이터 구조 선택 이유·저장 정책 반영"
git push
```

### 커밋 #26 — 단계별 스크린샷 삽입 (피드백 1)

기본 가이드에서 `docs/screenshots/screenshot_01.png` ~ `screenshot_23.png` 를 이미 올렸다. 여기서는 **재촬영·추가 촬영** 후 README 에 삽입한다.

**1) 재촬영·추가 촬영 체크리스트** — 파일 이름을 아래와 같이 `docs/screenshots/` 에 저장한다. (`Win + Shift + S`)

| 파일 | 구분 | 촬영 내용 | 방법 |
|---|---|---|---|
| `screenshot_02.png` | 재촬영 | `gh auth login` 화면의 일회용 코드 가리기 | 이미지 편집기로 코드 부분을 모자이크 |
| `screenshot_03.png` | 재촬영 | `mkdir`, `git init`, 기본 브랜치 `main` 확인 | **`prompt-manager` 폴더 안**에서 보이도록. 이미 초기화했다면 임시 폴더(`C:\dev\git\andrewjung376\init-demo`)에서 재현하고 캡처 후 삭제 |
| `screenshot_06.png` | 재촬영 | **샘플 저장소** clone | 기본 가이드 4장 명령으로 `Spoon-Knife` 를 받고 `dir`, `git log --oneline -5` 까지 캡처 |
| `screenshot_24.png` | 추가 | 제목 중복 거부 | 7장 T11 또는 T12 |
| `screenshot_25.png` | 추가 | 추가 전 확인 `y`/`n` | 7장 T13 |
| `screenshot_26.png` | 추가 | JSON 저장 후 재실행해도 유지 | 7장 T14 (파일 내용 포함) |
| `screenshot_27.png` | 추가 | 손상 파일 복구 | 7장 T15 |
| `screenshot_28.png` | 추가 | Markdown 내보내기 결과 | 7장 T16 |
| `screenshot_29.png` | 추가 | 프롬프트 수정 | 7장 T17 |
| `screenshot_30.png` | 추가 | 프롬프트 삭제 | 7장 T19 |
| `screenshot_31.png` | 추가 | 조회수 기록과 Top 목록 | 7장 T20 |
| `screenshot_32.png` | 추가 | 브랜치·병합 그래프 | `git log --oneline --graph -15` |
| `screenshot_33.png` | 추가 | VSCode Python 확장 설치와 GitHub 로그인 화면 | VSCode 확장 탭, 계정 메뉴 |

**2) README 맨 아래에 아래 절을 추가한다.**

````markdown
## 단계별 실행 예제

각 단계에서 실제로 실행한 화면입니다.

### 1. 개발 환경과 저장소 준비

**Python·Git 버전과 VSCode 확장 확인**

![Python 3.13.5, Git 2.47.0 버전과 한국어 팩·Python 확장 설치 확인](docs/screenshots/screenshot_01.png)

**VSCode 확장과 GitHub 로그인**

![VSCode Python 확장 설치와 GitHub 로그인 화면](docs/screenshots/screenshot_33.png)

**GitHub 로그인(`gh auth login`)과 저장소 생성(`gh repo create`)**

![gh auth login 으로 로그인하고 prompt-manager 저장소를 생성](docs/screenshots/screenshot_02.png)

**저장소 초기화(`git init`)와 기본 브랜치 `main`**

![git init 후 기본 브랜치를 main 으로 변경](docs/screenshots/screenshot_03.png)

**`.gitignore` 와 `README.md` 생성**

![.gitignore 와 README.md 를 만들고 내용 확인](docs/screenshots/screenshot_04.png)

**첫 커밋과 `push`**

![첫 커밋을 만들고 원격 저장소에 push](docs/screenshots/screenshot_05.png)

**샘플 저장소 `clone`**

![공개 샘플 저장소를 clone 해 폴더 구조와 로그 확인](docs/screenshots/screenshot_06.png)

### 2. 필수 기능 구현

**메뉴 출력과 종료 (커밋 #2)**

![메뉴를 출력하고 0 을 입력해 종료](docs/screenshots/screenshot_07.png)
![메뉴 출력 기능 커밋과 push](docs/screenshots/screenshot_08.png)

**잘못된 메뉴 입력 처리 (커밋 #3)**

![잘못된 번호와 문자를 입력하면 안내 후 메뉴를 다시 출력](docs/screenshots/screenshot_09.png)
![잘못된 입력 처리 커밋과 push](docs/screenshots/screenshot_10.png)

**기본 프롬프트 5개 등록 (커밋 #4)**

![기본 프롬프트 5개 등록 확인과 커밋](docs/screenshots/screenshot_11.png)

**입력 검증 함수 (커밋 #5)**

![빈 입력은 다시 입력받는 함수 확인과 커밋](docs/screenshots/screenshot_12.png)

**프롬프트 추가 (커밋 #6)**

![빈 제목은 재입력, 입력 완료 후 추가 메시지, 커밋과 push](docs/screenshots/screenshot_13.png)

**목록 — 브랜치 작업 (커밋 #7)**

![feature/prompt-list 브랜치에서 목록 기능 구현, 커밋과 push](docs/screenshots/screenshot_14.png)

**브랜치 병합 (커밋 #8)**

![main 으로 병합하고 git log --graph 로 병합 갈래 확인](docs/screenshots/screenshot_15.png)

**카테고리별 조회 (커밋 #9)**

![카테고리별 조회와 잘못된 번호 재입력](docs/screenshots/screenshot_16.png)

**검색 (커밋 #10)**

![키워드 검색과 결과 없음 안내](docs/screenshots/screenshot_17.png)

**상세 보기 (커밋 #11)**

![번호로 상세 보기와 잘못된 번호 안내](docs/screenshots/screenshot_18.png)

**즐겨찾기 (커밋 #12)**

![즐겨찾기 추가·해제와 즐겨찾기 목록](docs/screenshots/screenshot_19.png)
![즐겨찾기 기능 커밋과 push](docs/screenshots/screenshot_20.png)

**README 작성과 `pull`**

![README 작성 후 커밋과 push](docs/screenshots/screenshot_21.png)
![GitHub 웹에서 수정한 README 를 git pull 로 가져오기](docs/screenshots/screenshot_22.png)

### 3. 필수 기능 보완

**제목 중복 검사**

![같은 제목을 입력하면 기존 항목을 보여 주고 취소하거나 다른 제목을 입력](docs/screenshots/screenshot_24.png)

**추가 전 확인**

![입력 내용 요약 후 y/n 으로 확인, n 이면 추가 취소](docs/screenshots/screenshot_25.png)

### 4. 보너스 1 — 영속화와 내보내기

**JSON 저장 후 재실행해도 유지**

![추가한 프롬프트가 data/prompts.json 에 저장되고 재실행해도 목록에 남음](docs/screenshots/screenshot_26.png)

**손상된 저장 파일 복구**

![손상된 JSON 은 .bak 으로 보관하고 기본 데이터로 시작](docs/screenshots/screenshot_27.png)

**카테고리별 Markdown 내보내기**

![카테고리별 .md 파일 생성과 내용 확인](docs/screenshots/screenshot_28.png)

### 5. 보너스 2 — 수정·삭제·조회수

**수정**

![제목·내용 수정과 변경 내용 확인](docs/screenshots/screenshot_29.png)

**삭제**

![삭제 확인(y/n) 후 삭제, 번호가 당겨짐](docs/screenshots/screenshot_30.png)

**조회수와 Top 목록**

![상세 보기마다 조회수가 오르고 Top 목록에 순위 표시](docs/screenshots/screenshot_31.png)

### 6. 최종 상태

**작업 트리와 커밋 그래프**

![git status 와 git log --oneline --graph 로 최종 이력 확인](docs/screenshots/screenshot_23.png)
![feature/bonus-json, feature/bonus-crud 병합까지 포함한 최종 그래프](docs/screenshots/screenshot_32.png)
````

**3) 이미지 링크 확인** — 깨진 링크가 없는지 검사한다. (빈 목록 `[]` 이 나오면 정상)

**공통**

```bash
python -c "import re,os; t=open('README.md',encoding='utf-8').read(); print([p for p in re.findall(r'docs/screenshots/\S+?\.png', t) if not os.path.exists(p)])"
```

VSCode 에서 `Ctrl+Shift+V` 로 미리보기를 열어 이미지가 보이는지도 확인한다.

**4) 커밋**

**공통**

```bash
git add README.md docs/screenshots
git commit -m "docs: README에 단계별 실행 스크린샷 삽입"
git push
```

---

## 7. 수용 기준 검증 T11~T22

`prompt-manager` 폴더에서 실행한다. 시험은 `--data` 로 **별도 파일**(`data/test.json`)을 쓰므로 실제 저장 파일(`data/prompts.json`)은 건드리지 않는다.

### 준비

**Bash**

```bash
mkdir -p data
t() { rm -rf data/export_test; rm -f data/test.json; printf "$1" | python prompt_manager.py --data data/test.json --export-dir data/export_test; }
```

**cmd**

```bat
if not exist data mkdir data
set OPT=--data data\test.json --export-dir data\export_test
```

cmd 의 각 시험 줄은 `rmdir ... & del ... & (...) | python ...` 형태다. 앞의 두 명령이 시험 파일을 비운 뒤 입력을 전달한다.

### 기존 시험 T3~T5 (확인 단계 `y` 추가)

추가 흐름에 확인 단계가 생겨 입력에 `y` 가 하나 늘었다. T1, T2, T6~T10 은 기본 가이드의 명령 끝에 `--data data/test.json` 만 붙여 실행한다.

**Bash**

```bash
t '1\n   \n제목\n내용\n1\ny\n0\n'                      # T3
t '1\n제목\n내용\n1\ny\n2\n0\n'                        # T4
t '1\n제목\n내용\n7\n코딩\ny\n3\n7\n0\n'               # T5
```

**cmd**

```bat
rmdir /s /q data\export_test 2>nul & del data\test.json 2>nul & (echo 1& echo.& echo 제목& echo 내용& echo 1& echo y& echo 0) | python prompt_manager.py %OPT%
rmdir /s /q data\export_test 2>nul & del data\test.json 2>nul & (echo 1& echo 제목& echo 내용& echo 1& echo y& echo 2& echo 0) | python prompt_manager.py %OPT%
rmdir /s /q data\export_test 2>nul & del data\test.json 2>nul & (echo 1& echo 제목& echo 내용& echo 7& echo 코딩& echo y& echo 3& echo 7& echo 0) | python prompt_manager.py %OPT%
```

### 새 시험 T11~T22

**Bash**

```bash
t '1\n블로그 글 작성 도우미\nn\n2\n0\n'                            # T11 중복 제목 거부
t '1\n블로그 글 작성 도우미\ny\n새 제목\n내용\n1\ny\n2\n0\n'       # T12 중복 후 재입력
t '1\n제목\n내용\n1\nn\n2\n0\n'                                    # T13 추가 확인에서 취소

# T14 저장 후 재실행해도 유지 (같은 파일로 두 번 실행)
rm -f data/test.json
printf '1\n저장 테스트\n내용\n7\n코딩\ny\n0\n' | python prompt_manager.py --data data/test.json
printf '2\n0\n' | python prompt_manager.py --data data/test.json
cat data/test.json

# T15 손상된 파일 복구
rm -f data/test.json data/test.json.bak
echo '{broken' > data/test.json
printf '2\n0\n' | python prompt_manager.py --data data/test.json
ls data

# T16 Markdown 내보내기 (카테고리 이름의 특수문자 치환 포함)
t '1\n제목 A\n내용 첫줄\n7\na/b:c\ny\n8\n0\n'
ls data/export_test
cat data/export_test/a_b_c.md

t '9\n2\n새 썸네일\n새 내용입니다\nn\ny\n2\n0\n'                   # T17 수정
t '9\n2\n블로그 글 작성 도우미\n\n\nn\n0\n'                         # T18 수정 중복 거부, 변경 없음
t '10\n2\ny\n2\n0\n'                                                # T19 삭제
t '10\n2\nn\n2\n0\n'                                                # T19 삭제 취소
t '5\n2\n5\n2\n5\n1\n11\n0\n'                                       # T20 조회수와 Top
t '11\n0\n'                                                         # T21 Top 비어 있음

# T22 구버전 파일(views 없음) 호환
rm -f data/test.json
python -c "import json; json.dump({'version':1,'categories':['기타'],'prompts':[{'title':'옛 데이터','content':'c','category':'기타','favorite':False}]}, open('data/test.json','w',encoding='utf-8'), ensure_ascii=False)"
printf '5\n1\n0\n' | python prompt_manager.py --data data/test.json

# 정리
rm -rf data/export_test data/test.json data/test.json.bak
```

**cmd**

```bat
rmdir /s /q data\export_test 2>nul & del data\test.json 2>nul & (echo 1& echo 블로그 글 작성 도우미& echo n& echo 2& echo 0) | python prompt_manager.py %OPT%
rmdir /s /q data\export_test 2>nul & del data\test.json 2>nul & (echo 1& echo 블로그 글 작성 도우미& echo y& echo 새 제목& echo 내용& echo 1& echo y& echo 2& echo 0) | python prompt_manager.py %OPT%
rmdir /s /q data\export_test 2>nul & del data\test.json 2>nul & (echo 1& echo 제목& echo 내용& echo 1& echo n& echo 2& echo 0) | python prompt_manager.py %OPT%

REM T14 저장 후 재실행해도 유지 (같은 파일로 두 번 실행)
del data\test.json 2>nul
(echo 1& echo 저장 테스트& echo 내용& echo 7& echo 코딩& echo y& echo 0) | python prompt_manager.py %OPT%
(echo 2& echo 0) | python prompt_manager.py %OPT%
type data\test.json

REM T15 손상된 파일 복구
del data\test.json data\test.json.bak 2>nul
echo {broken> data\test.json
(echo 2& echo 0) | python prompt_manager.py %OPT%
dir /b data

REM T16 Markdown 내보내기 (카테고리 이름의 특수문자 치환 포함)
rmdir /s /q data\export_test 2>nul & del data\test.json 2>nul & (echo 1& echo 제목 A& echo 내용 첫줄& echo 7& echo a/b:c& echo y& echo 8& echo 0) | python prompt_manager.py %OPT%
dir /b data\export_test
type data\export_test\a_b_c.md

rmdir /s /q data\export_test 2>nul & del data\test.json 2>nul & (echo 9& echo 2& echo 새 썸네일& echo 새 내용입니다& echo n& echo y& echo 2& echo 0) | python prompt_manager.py %OPT%
rmdir /s /q data\export_test 2>nul & del data\test.json 2>nul & (echo 9& echo 2& echo 블로그 글 작성 도우미& echo.& echo.& echo n& echo 0) | python prompt_manager.py %OPT%
rmdir /s /q data\export_test 2>nul & del data\test.json 2>nul & (echo 10& echo 2& echo y& echo 2& echo 0) | python prompt_manager.py %OPT%
rmdir /s /q data\export_test 2>nul & del data\test.json 2>nul & (echo 10& echo 2& echo n& echo 2& echo 0) | python prompt_manager.py %OPT%
rmdir /s /q data\export_test 2>nul & del data\test.json 2>nul & (echo 5& echo 2& echo 5& echo 2& echo 5& echo 1& echo 11& echo 0) | python prompt_manager.py %OPT%
rmdir /s /q data\export_test 2>nul & del data\test.json 2>nul & (echo 11& echo 0) | python prompt_manager.py %OPT%

REM T22 구버전 파일(views 없음) 호환
del data\test.json 2>nul
python -c "import json; json.dump({'version':1,'categories':['기타'],'prompts':[{'title':'옛 데이터','content':'c','category':'기타','favorite':False}]}, open('data/test.json','w',encoding='utf-8'), ensure_ascii=False)"
(echo 5& echo 1& echo 0) | python prompt_manager.py %OPT%

REM 정리
rmdir /s /q data\export_test 2>nul & del data\test.json data\test.json.bak 2>nul
```

cmd 블록의 `REM` 줄은 설명이다. 명령은 위에서부터 T11, T12, T13, T14, T15, T16, T17, T18, T19(삭제), T19(취소), T20, T21, T22 순서다.

### 기대 결과

| # | 기대 결과 |
|---|---|
| T3 | `값을 입력해야 합니다.` 후 확인 `y` 로 추가 완료 |
| T4 | 목록 6번에 `[텍스트 생성] 제목` (⭐ 없음) |
| T5 | 카테고리 목록에 `7) 코딩`, 조회 결과에 `[코딩] 제목` |
| T11 | `이미 같은 제목의 프롬프트가 있습니다: 1. ...` → `추가를 취소했습니다.` → `총 5개의 프롬프트` |
| T12 | 중복 안내 후 `y` 로 새 제목 입력 → 목록 6번에 `새 제목` |
| T13 | 확인 요약 출력 후 `추가를 취소했습니다.` → `총 5개의 프롬프트` |
| T14 | 첫 실행 후 `data/test.json` 생성(`"version": 2`), 재실행 목록에 `6. [코딩] 저장 테스트`, 카테고리 `7) 코딩` 유지 |
| T15 | `저장 파일을 읽을 수 없어 기본 데이터로 시작합니다.` → `총 5개의 프롬프트`, `data` 에 `test.json.bak` |
| T16 | `총 6개 파일을 내보냈습니다.`, `a_b_c.md` 생성, 내용에 `# a/b:c` 와 `> 내용 첫줄` |
| T17 | 변경 요약(`제목: 제품 썸네일 생성 -> 새 썸네일`) 후 `프롬프트가 수정되었습니다!`, 목록 2번 `새 썸네일` |
| T18 | 중복 안내 후 Enter 로 유지 → `변경된 내용이 없습니다.` |
| T19 | 삭제: `삭제했습니다` → `총 4개의 프롬프트` / 취소: `삭제를 취소했습니다.` → `총 5개의 프롬프트` |
| T20 | `조회수: 1`, `조회수: 2` 후 `1위 (번호 2) ... 조회 2회`, `2위 (번호 1) ... 조회 1회` |
| T21 | `아직 조회 기록이 없습니다.` |
| T22 | 옛 파일도 불러와지고 상세 보기에서 `조회수: 1` |

---

## 8. 제출물 준비

### 8-1. 최종 상태 확인

**공통**

```bash
git status
git log --oneline --graph
git branch -a
git remote -v
```

체크리스트:

- [ ] `git status` → `nothing to commit, working tree clean`
- [ ] 커밋 10개 이상 (이 문서까지 총 28개: 기본 #1~#13 + 웹 수정 1 + 스크린샷 1 + 이 문서 #14~#26)
- [ ] 그래프에 `feature/bonus-json`, `feature/bonus-crud` 두 번의 병합 갈래(`|\` … `|/`)
- [ ] `data/`, `exports/` 가 저장소에 올라가지 않음 (`git ls-files data exports` 가 비어 있음)
- [ ] GitHub 저장소 README 에서 스크린샷이 모두 보임
- [ ] 7장 T3~T5, T11~T22 와 기본 가이드 T1, T2, T6~T10 을 모두 확인

기대 출력 형태 (해시는 실제와 다름, 위가 최신):

```text
* a1b2c3d docs: README에 단계별 실행 스크린샷 삽입
* b2c3d4e docs: README 보너스 기능·데이터 구조 선택 이유·저장 정책 반영
*   c3d4e5f Merge branch 'feature/bonus-crud'
|\
| * d4e5f6a feat: 조회수 Top 목록
| * e5f6a7b feat: 상세 보기 조회수 기록
| * f6a7b8c feat: 프롬프트 삭제
| * a7b8c9d feat: 프롬프트 수정
|/
*   b8c9d0e Merge branch 'feature/bonus-json'
|\
| * c9d0e1f feat: 카테고리별 Markdown 내보내기
| * d0e1f2a feat: JSON 영속화 (저장·불러오기, 손상 복구)
|/
* e1f2a3b chore: .gitignore를 data/·exports/ 기준으로 조정
* f2a3b4c feat: 프롬프트 추가 전 확인 절차
* a3b4c5d feat: 프롬프트 추가 시 제목 중복 검사
* b4c5d6e docs: 제출용 스크린샷 추가
* c5d6e7f Update README.md
* d6e7f8a docs: README 기능 목록·실행 방법·카테고리 설명 작성
  ... (기본 가이드의 커밋 #1~#13, feature/prompt-list 병합 포함)
```

### 8-2. 제출물 목록

| 제출물 | 준비 방법 |
|---|---|
| GitHub 저장소 URL | `https://github.com/andrewjung376/prompt-manager` |
| 개발 환경 스크린샷 | 기본 가이드 1장, 6장 #26 의 `screenshot_01`, `screenshot_33` |
| 프로그램 실행 스크린샷 | 메뉴, 추가, 목록, 검색에 더해 중복 검사, 확인 절차, 저장 유지, 내보내기, 수정, 삭제, Top 목록 (6장 #26 표) |
| `git log --oneline --graph` 스크린샷 | 8-1 출력 (`screenshot_32`). 병합 갈래 두 개가 모두 보이도록 터미널 창을 넓게 |
| README | 단계별 스크린샷, 데이터 구조 선택 이유, 저장 정책 포함 |

---

## 9. 문제 해결 (추가분)

기본 가이드 10장의 항목도 함께 참고한다.

| 증상 | 원인 | 해결 |
|---|---|---|
| `KeyError: 'views'` | #22 의 세 군데 중 일부를 적용하지 않음 | 기본 데이터(`dict(p, views=0)`), `add_prompt()` 의 `"views": 0`, `show_detail()` 를 모두 적용했는지 확인 |
| `NameError: name 'save_data' is not defined` | #17 의 새 함수 붙여넣기 누락 | `def main():` 위에 `get_option` ~ `save_data` 가 있는지 확인 |
| `NameError: name 'confirm' is not defined` | #14 함수 누락 | #14 의 새 함수를 붙여넣었는지 확인 |
| 기본 가이드의 T3~T5 가 중간에서 멈추거나 다른 결과 | 추가 흐름에 확인 단계(`y`) 추가됨 | 7장의 T3~T5 입력 사용 |
| 시험 결과가 매번 달라짐 | 시험이 실제 저장 파일을 공유 | 모든 시험에 `--data data/test.json` 사용, 시험 전 파일 삭제 |
| `git status` 에 `data/` 가 보임 | `.gitignore` 미적용 | #16 을 먼저 적용했는지 확인. 이미 추적 중이면 `git rm -r --cached data` 후 커밋 |
| `저장 파일을 읽을 수 없어 기본 데이터로 시작합니다.` | 저장 파일 손상(직접 편집 오류 등) | 원본은 `.bak` 에 있다. 내용을 고쳐 `.json` 으로 되돌리면 복구된다 |
| `저장에 실패했습니다.` | 폴더 쓰기 권한 없음, 경로 오류 | `--data` 경로를 확인한다. 이번 실행은 메모리로 계속 동작한다 |
| 내보낸 파일 이름이 `_` 로 바뀜 | 카테고리 이름에 `\ / : * ? " < > \|` 포함 | 정상 동작(Windows 파일명 규칙). 내용의 `# 카테고리` 제목은 원래 이름 그대로 |
| 삭제 후 번호가 바뀜 | 번호는 목록 위치 | 정상 동작. 삭제 후에는 목록(메뉴 2)에서 번호를 다시 확인 |
| cmd 에서 `del` 이 파일을 찾을 수 없다고 함 | 삭제할 파일이 없음 | `2>nul` 로 숨긴 메시지이므로 무시해도 된다 |
| `git push` 가 새 브랜치에서 upstream 오류 | 브랜치 첫 push | `git push -u origin <브랜치명>` |
