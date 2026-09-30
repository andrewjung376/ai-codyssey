# CLI 실행 가이드: 프롬프트 관리 프로그램 제출물 + Git 전략 실행

> 근거 문서: [project.md](../project.md), [prd.md](prd.md)
>
> 이 문서는 [prd.md](prd.md)를 충족하는 **제출물**(프로그램·GitHub 저장소·README·스크린샷)과 **Git 전략**(13개 커밋, 브랜치 생성·병합, 8개 명령어 사용)을 터미널 명령으로 순서대로 실행할 수 있게 정리한 가이드다.
>
> - 결과물은 `ai-codyssey` 저장소 **밖**의 새 폴더 `C:\dev\git\andrewjung376\prompt-manager`에 만든다. (저장소 중첩 방지)
> - 명령은 **Git Bash** 기준이다. VSCode 통합 터미널을 Git Bash로 열면 된다. PowerShell 차이는 각 절에 표시했다.
> - 코드 삽입은 VSCode에서 붙여넣는다. 붙여넣은 뒤에는 반드시 **실행 확인 → 커밋** 순서를 지킨다.

## 진행 요약

| 단계 | 내용 | prd.md 대응 | 커밋 |
|---|---|---|---|
| 1 | 개발 환경 확인 | §8 | – |
| 2 | GitHub 저장소 생성 | §7 저장소 | – |
| 3 | `init`, 첫 커밋, `push` | §7 | #1 |
| 4 | `clone` 실습 | §7 명령어 | – |
| 5 | 기능 구현 커밋 | §4, §6 | #2~#13 |
| 6 | `pull` 실습 | §7 명령어 | (원격 커밋 1개) |
| 7 | 수용 기준 T1~T10 검증 | §10 | – |
| 8 | 제출물 준비 | §11 | – |

---

## 1. 개발 환경 확인 (prd §8)

```bash
python --version
git --version
git config --global user.name "andrewjung376"
git config --global user.email "<GitHub 계정 이메일>"
git config --global init.defaultBranch main
git config --global core.autocrlf true
git config --global --list
code --install-extension ms-python.python
code --install-extension MS-CEINTL.vscode-language-pack-ko
code --list-extensions | grep -i -E "python|language-pack-ko"
```

- `MS-CEINTL...ko`(한국어 팩)는 선택 사항이다.
- `core.autocrlf true`는 Windows에서 나오는 `LF will be replaced by CRLF` 경고를 줄여 준다.

`Hello` 실행 확인 (별도 임시 폴더에서 수행하고 프로젝트 폴더에는 만들지 않는다):

```bash
mkdir -p ~/hello-test && cd ~/hello-test
echo 'print("Hello")' > hello.py
python hello.py
cd ~ && rm -rf ~/hello-test
```

VSCode GitHub 로그인: 좌측 하단 **계정(Accounts)** 아이콘 → GitHub 로그인 항목을 선택해 브라우저에서 인증한다. 로그인 후 계정 메뉴에 `andrewjung376` 이 표시되면 연동이 정상이다. (터미널 대안: `gh auth login` → `gh auth status`)

**스크린샷 ①(개발 환경):** VSCode 창에 Python 확장 설치 화면 + 터미널의 `python --version`, `git --version`, `git config --global --list` 출력이 함께 보이게 캡처한다.

---

## 2. GitHub 새 저장소 생성 (prd §7 저장소)

### 방법 A: 웹

1. <https://github.com/new> 접속
2. Repository name: `prompt-manager`, **Public**
3. *Add a README file*, *.gitignore*, *license* 는 **모두 체크 해제**한다. (로컬에서 만들어 첫 push 충돌을 피한다)
4. *Create repository* 클릭

### 방법 B: GitHub CLI

```bash
gh auth login
gh repo create prompt-manager --public
```

저장소 URL: `https://github.com/andrewjung376/prompt-manager.git`

---

## 3. 로컬 저장소 초기화와 첫 커밋 — `init`, `add`, `commit`, `push` (커밋 #1)

```bash
cd /c/dev/git/andrewjung376
mkdir prompt-manager
cd prompt-manager
git init
git branch --show-current
```

`main` 이 출력되어야 한다. (`master` 라면 `git branch -M main`)

`.gitignore` 와 `README.md` 생성:

```bash
cat > .gitignore <<'EOF'
__pycache__/
*.pyc
.venv/
.vscode/
*.json
EOF

cat > README.md <<'EOF'
# 나만의 프롬프트 관리 프로그램
EOF
```

원격 연결 후 첫 push:

```bash
git add .gitignore README.md
git commit -m "chore: 프로젝트 초기화 (.gitignore, README 제목)"
git remote add origin https://github.com/andrewjung376/prompt-manager.git
git remote -v
git push -u origin main
```

---

## 4. 샘플 저장소 내려받기 — `clone` (prd §7)

프로젝트 폴더 **밖**에서 실행한다.

```bash
cd /c/dev/git/andrewjung376
git clone https://github.com/octocat/Spoon-Knife.git
cd Spoon-Knife
ls -la
git log --oneline -5
cd ..
rm -rf Spoon-Knife
cd prompt-manager
```

> PowerShell에서 삭제할 때는 `Remove-Item -Recurse -Force Spoon-Knife`

---

## 5. 기능 구현과 커밋 (#2 ~ #13)

모든 작업은 `prompt-manager` 폴더에서 한다. 코드는 `prompt_manager.py` **한 파일**에 함수로 분리한다. (prd §6)

각 단계의 공통 규칙:

1. 코드 작성 → 2. `python prompt_manager.py` 로 실행 확인 → 3. `git add` / `git commit` / `git push`
4. 함수는 **`def main():` 바로 위**에 붙여넣는다. (Python은 함수 호출 시점에 이름을 찾으므로 정의 순서는 `main()` 실행 전이면 된다)

### 커밋 #2 — 메뉴 출력, 메인 루프, 종료

```bash
cat > prompt_manager.py <<'EOF'
"""나만의 프롬프트 관리 프로그램 (콘솔 기반)"""


def show_menu():
    print("\n=== 나만의 프롬프트 관리 ===")
    print("1. 프롬프트 추가")
    print("2. 프롬프트 목록")
    print("3. 카테고리별 조회")
    print("4. 프롬프트 검색")
    print("5. 프롬프트 상세 보기")
    print("6. 즐겨찾기 관리")
    print("7. 즐겨찾기 목록")
    print("0. 종료")


def main():
    try:
        while True:
            show_menu()
            choice = input("선택: ").strip()
            if choice == "0":
                print("프로그램을 종료합니다.")
                break
    except (KeyboardInterrupt, EOFError):
        print("\n프로그램을 종료합니다.")


if __name__ == "__main__":
    main()
EOF

printf '0\n' | python prompt_manager.py
git add prompt_manager.py
git commit -m "feat: 메뉴 출력 및 메인 루프, 종료 기능"
git push
```

### 커밋 #3 — 잘못된 메뉴 입력 처리

`main()` 의 `if choice == "0": ... break` 블록 **아래**에 `else` 를 추가한다.

```python
            if choice == "0":
                print("프로그램을 종료합니다.")
                break
            else:
                print("올바른 번호를 입력하세요.")
```

```bash
printf '9\nabc\n\n0\n' | python prompt_manager.py
git add prompt_manager.py
git commit -m "feat: 잘못된 메뉴 입력 처리"
git push
```

`올바른 번호를 입력하세요.` 가 3번 출력되고 종료되면 정상이다.

### 커밋 #4 — 이전 미션 프롬프트 기본 데이터 등록 (F1)

docstring 바로 아래(`def show_menu():` 위)에 붙여넣는다.

> **중요:** 아래 5개는 예시다. 실제 제출 전에 **이전 미션에서 작성한 본인의 프롬프트**로 `title`, `content`, `category` 를 바꿔 넣는다. (최소 3개 필요)

```python
CATEGORIES = ["텍스트 생성", "이미지 생성", "영상 생성", "페르소나", "자동화", "기타"]

DEFAULT_PROMPTS = [
    {
        "title": "블로그 글 작성 도우미",
        "content": "당신은 10년 경력의 전문 블로거입니다. 주어진 주제에 대해 SEO에 최적화된 블로그 글을 작성해주세요. 서론, 본론, 결론 구조를 갖추고, 독자의 관심을 끄는 제목을 3개 제안해주세요.",
        "category": "텍스트 생성",
        "favorite": True,
    },
    {
        "title": "제품 썸네일 생성",
        "content": "다음 제품의 매력적인 썸네일 이미지를 생성해주세요. 밝은 스튜디오 조명, 깔끔한 흰색 배경, 제품이 중앙에 크게 보이는 구도, 고해상도.",
        "category": "이미지 생성",
        "favorite": False,
    },
    {
        "title": "광고 스크립트 작성",
        "content": "15초 분량의 제품 광고 영상 스크립트를 작성해주세요. 장면별 화면 묘사, 내레이션, 자막을 표 형식으로 정리해주세요.",
        "category": "영상 생성",
        "favorite": False,
    },
    {
        "title": "IT 컨설턴트 페르소나",
        "content": "당신은 15년 경력의 IT 컨설턴트입니다. 비전문가도 이해할 수 있게 쉬운 비유로 설명하고, 답변 끝에 실행 가능한 다음 단계 3가지를 제시해주세요.",
        "category": "페르소나",
        "favorite": False,
    },
    {
        "title": "뉴스 요약 프롬프트",
        "content": "아래 뉴스 기사를 3줄로 요약하고, 핵심 키워드 5개와 독자가 알아야 할 시사점 1가지를 덧붙여주세요.",
        "category": "자동화",
        "favorite": False,
    },
]

categories = list(CATEGORIES)
prompts = [dict(p) for p in DEFAULT_PROMPTS]
```

```bash
python -c "import prompt_manager as m; print(len(m.prompts), '개 등록')"
git add prompt_manager.py
git commit -m "feat: 이전 미션 프롬프트 기본 데이터 등록"
git push
```

`5 개 등록` (3 이상) 이 출력되면 정상이다.

### 커밋 #5 — 입력 검증 헬퍼 함수

```python
def input_non_empty(message):
    while True:
        value = input(message).strip()
        if value:
            return value
        print("값을 입력해야 합니다. 다시 입력하세요.")


def input_number(message, min_value, max_value, retry=False):
    while True:
        value = input(message).strip()
        if value.isdigit() and min_value <= int(value) <= max_value:
            return int(value)
        print(f"{min_value}~{max_value} 사이의 번호를 입력하세요.")
        if not retry:
            return None


def select_category(allow_custom=False):
    for number, name in enumerate(categories, 1):
        print(f"{number}) {name}")
    custom_no = len(categories) + 1
    if allow_custom:
        print(f"{custom_no}) 직접 입력")
    last_no = custom_no if allow_custom else len(categories)
    selected = input_number("선택: ", 1, last_no, retry=True)
    if allow_custom and selected == custom_no:
        name = input_non_empty("새 카테고리 이름: ")
        if name not in categories:
            categories.append(name)
        return name
    return categories[selected - 1]
```

- `input_number(..., retry=False)`: 잘못된 값이면 `None` 반환 (상세 보기·즐겨찾기용, prd F6/F7)
- `input_number(..., retry=True)`: 올바른 값이 나올 때까지 재입력 (카테고리 선택용, prd F2/F4)

```bash
printf '\n  \n값\n' | python -c "import prompt_manager as m; print(repr(m.input_non_empty('입력: ')))"
git add prompt_manager.py
git commit -m "feat: 입력 검증 헬퍼 함수 추가"
git push
```

빈 입력 2번에 재입력 안내가 나오고 `'값'` 이 출력되면 정상이다.

### 커밋 #6 — 프롬프트 추가 (F2)

함수를 추가하고, `main()` 의 `if choice == "0":` 블록과 `else:` 사이에 분기를 넣는다.

```python
def add_prompt():
    print("\n=== 프롬프트 추가 ===")
    title = input_non_empty("제목: ")
    content = input_non_empty("내용: ")
    print("\n카테고리 선택:")
    category = select_category(allow_custom=True)
    prompts.append(
        {"title": title, "content": content, "category": category, "favorite": False}
    )
    print("\n프롬프트가 추가되었습니다!")
```

```python
            elif choice == "1":
                add_prompt()
```

```bash
printf '1\n   \n테스트 제목\n테스트 내용\n1\n0\n' | python prompt_manager.py
git add prompt_manager.py
git commit -m "feat: 프롬프트 추가 기능"
git push
```

공백 제목에 재입력 안내가 나온 뒤 `프롬프트가 추가되었습니다!` 가 출력되면 정상이다. (T3)

### 커밋 #7 — 프롬프트 목록 (F3) : **브랜치에서 작업** (`checkout`)

먼저 `main` 을 push한 상태인지 확인한 뒤 브랜치를 만든다.

```bash
git status
git checkout -b feature/prompt-list
git branch
```

`* feature/prompt-list` 가 보이면 성공이다. 이 브랜치에서 아래 코드를 작성한다.

```python
def format_prompt_line(number, prompt):
    star = " ⭐" if prompt["favorite"] else ""
    return f"{number}. [{prompt['category']}] {prompt['title']}{star}"


def print_prompt_lines(items):
    for number, prompt in items:
        print(format_prompt_line(number, prompt))


def show_list():
    print("\n=== 프롬프트 목록 ===")
    if not prompts:
        print("등록된 프롬프트가 없습니다.")
        return
    print_prompt_lines(list(enumerate(prompts, 1)))
    print(f"\n총 {len(prompts)}개의 프롬프트")
```

```python
            elif choice == "2":
                show_list()
```

`items` 는 `(전체 번호, 프롬프트)` 튜플의 리스트다. 이후 조회·검색·즐겨찾기 목록에서도 이 함수를 재사용한다.

```bash
printf '2\n0\n' | python prompt_manager.py
git add prompt_manager.py
git commit -m "feat: 프롬프트 목록 기능"
git push -u origin feature/prompt-list
```

### 커밋 #8 — `main` 으로 병합 (`checkout`, `merge`)

```bash
git checkout main
git merge --no-ff feature/prompt-list -m "Merge branch 'feature/prompt-list'"
git push
git log --oneline --graph -5
```

- `--no-ff` 를 쓰면 fast-forward 대신 **병합 커밋**이 만들어져 `git log --graph` 에 갈래(`|\`, `|/`)가 남는다.
- 충돌이 나면 `git status` 로 `both modified` 파일을 확인하고, `<<<<<<<` / `=======` / `>>>>>>>` 구간을 VSCode에서 정리한 뒤 `git add prompt_manager.py` → `git commit` 한다.
- 병합 후 브랜치 정리(선택):

```bash
git branch -d feature/prompt-list
git push origin --delete feature/prompt-list
```

> 원격 브랜치를 삭제해도 `git log --graph` 의 병합 기록은 그대로 남는다.

### 커밋 #9 — 카테고리별 조회 (F4)

```python
def show_by_category():
    print("\n=== 카테고리별 조회 ===")
    category = select_category()
    items = [(n, p) for n, p in enumerate(prompts, 1) if p["category"] == category]
    if not items:
        print(f"\n[{category}] 카테고리에 등록된 프롬프트가 없습니다.")
        return
    print(f"\n[{category}] 카테고리 프롬프트:")
    print_prompt_lines(items)
    print(f"\n총 {len(items)}개의 프롬프트")
```

```python
            elif choice == "3":
                show_by_category()
```

```bash
printf '3\n9\n1\n0\n' | python prompt_manager.py
git add prompt_manager.py
git commit -m "feat: 카테고리별 조회 기능"
git push
```

잘못된 번호(9)에 재입력 안내가 나온 뒤 `[텍스트 생성]` 목록이 출력되어야 한다. 표시 번호는 **전체 목록 기준 번호**다.

### 커밋 #10 — 프롬프트 검색 (F5)

```python
def search_prompt():
    print("\n=== 프롬프트 검색 ===")
    keyword = input_non_empty("검색어: ").lower()
    items = [
        (n, p)
        for n, p in enumerate(prompts, 1)
        if keyword in p["title"].lower() or keyword in p["content"].lower()
    ]
    if not items:
        print("\n검색 결과가 없습니다.")
        return
    print("\n검색 결과:")
    print_prompt_lines(items)
    print(f"\n{len(items)}개의 프롬프트를 찾았습니다.")
```

```python
            elif choice == "4":
                search_prompt()
```

```bash
printf '4\n블로그\n4\n없는단어\n0\n' | python prompt_manager.py
git add prompt_manager.py
git commit -m "feat: 프롬프트 검색 기능"
git push
```

### 커밋 #11 — 프롬프트 상세 보기 (F6)

```python
def show_detail():
    print("\n=== 프롬프트 상세 보기 ===")
    if not prompts:
        print("등록된 프롬프트가 없습니다.")
        return
    number = input_number("번호 입력: ", 1, len(prompts))
    if number is None:
        return
    prompt = prompts[number - 1]
    line = "─" * 28
    print(f"\n{line}")
    print(f"제목: {prompt['title']}")
    print(f"카테고리: {prompt['category']}")
    print(f"즐겨찾기: {'⭐' if prompt['favorite'] else '-'}")
    print(line)
    print(f"내용:\n{prompt['content']}")
    print(line)
```

```python
            elif choice == "5":
                show_detail()
```

```bash
printf '5\n1\n5\n999\n0\n' | python prompt_manager.py
git add prompt_manager.py
git commit -m "feat: 프롬프트 상세 보기 기능"
git push
```

### 커밋 #12 — 즐겨찾기 관리와 목록 (F7, F8)

```python
def toggle_favorite():
    print("\n=== 즐겨찾기 관리 ===")
    if not prompts:
        print("등록된 프롬프트가 없습니다.")
        return
    number = input_number("프롬프트 번호 입력: ", 1, len(prompts))
    if number is None:
        return
    prompt = prompts[number - 1]
    prompt["favorite"] = not prompt["favorite"]
    state = "추가" if prompt["favorite"] else "해제"
    print(f"'{prompt['title']}' 프롬프트를 즐겨찾기에 {state}했습니다!")


def show_favorites():
    print("\n=== 즐겨찾기 목록 ===")
    items = [(n, p) for n, p in enumerate(prompts, 1) if p["favorite"]]
    if not items:
        print("즐겨찾기한 프롬프트가 없습니다.")
        return
    print_prompt_lines(items)
    print(f"\n총 {len(items)}개의 즐겨찾기")
```

```python
            elif choice == "6":
                toggle_favorite()
            elif choice == "7":
                show_favorites()
```

```bash
printf '6\n2\n6\n2\n7\n0\n' | python prompt_manager.py
git add prompt_manager.py
git commit -m "feat: 즐겨찾기 추가/해제 및 목록 기능"
git push
```

같은 번호를 두 번 입력하면 `추가했습니다!` → `해제했습니다!` 순서로 출력되어야 한다. (T8)

### 커밋 #13 — README 작성 (prd §9)

`README.md` 전체를 아래 내용으로 교체한다. (VSCode에서 붙여넣기)

````markdown
# 나만의 프롬프트 관리 프로그램

터미널에서 메뉴 번호를 입력해 프롬프트를 **추가·조회·검색·즐겨찾기**로 관리하는 Python 콘솔 프로그램입니다.
외부 라이브러리 없이 기본 문법(변수, 조건문, 반복문, 함수, 리스트, 딕셔너리)만 사용했습니다.

## 실행 환경

- Python 3.10 이상
- 추가 설치 패키지 없음

## 실행 방법

```bash
git clone https://github.com/andrewjung376/prompt-manager.git
cd prompt-manager
python prompt_manager.py
```

Windows에서 이모지(⭐)나 한글이 깨지면 `chcp 65001` 실행 후 다시 실행하세요.

## 기능 목록

| 메뉴 | 기능 | 설명 |
|---|---|---|
| 1 | 프롬프트 추가 | 제목, 내용, 카테고리를 입력해 등록 (빈 값 재입력, 카테고리 직접 입력 가능) |
| 2 | 프롬프트 목록 | 전체 프롬프트를 번호, 카테고리, 즐겨찾기(⭐)와 함께 출력 |
| 3 | 카테고리별 조회 | 카테고리를 선택해 해당 프롬프트만 출력 |
| 4 | 프롬프트 검색 | 키워드가 제목 또는 내용에 포함된 프롬프트 검색 (대소문자 무시) |
| 5 | 프롬프트 상세 보기 | 번호를 입력해 제목, 카테고리, 즐겨찾기, 내용 전체 출력 |
| 6 | 즐겨찾기 관리 | 번호를 입력해 즐겨찾기 추가/해제 |
| 7 | 즐겨찾기 목록 | 즐겨찾기한 프롬프트만 출력 |
| 0 | 종료 | 프로그램 종료 |

- 각 기능 실행 후에는 메뉴로 돌아옵니다.
- 잘못된 입력은 안내 메시지를 출력합니다.
- 조회·검색·즐겨찾기 목록의 번호는 **전체 목록 기준 번호**이므로, 그대로 상세 보기와 즐겨찾기 관리에 입력할 수 있습니다.
- 추가한 프롬프트와 즐겨찾기 상태는 실행 중에만 유지되며, 종료하면 기본 데이터로 초기화됩니다.

## 프롬프트 카테고리

| 카테고리 | 설명 |
|---|---|
| 텍스트 생성 | 글, 이메일, 요약 등 텍스트를 만드는 프롬프트 |
| 이미지 생성 | 이미지 생성 AI용 키워드와 지시문 |
| 영상 생성 | 영상 스크립트와 장면 구성 프롬프트 |
| 페르소나 | AI에게 역할과 말투를 부여하는 프롬프트 |
| 자동화 | 반복 업무와 워크플로 자동화용 프롬프트 |
| 기타 | 위에 속하지 않는 프롬프트 |
| (직접 입력) | 추가할 때 만든 새 카테고리. 실행 중 카테고리 목록에 함께 표시 |

## 기본 등록 프롬프트

프로그램 시작 시 이전 미션에서 작성한 프롬프트 5개가 미리 등록됩니다.

## 프로젝트 구조

```text
prompt-manager/
├── prompt_manager.py   # 프로그램 전체 (기능별 함수로 분리)
├── README.md
└── .gitignore
```

## 데이터 구조

```python
prompts = [
    {"title": "제목", "content": "내용", "category": "텍스트 생성", "favorite": False},
]
```
````

```bash
git add README.md
git commit -m "docs: README 기능 목록·실행 방법·카테고리 설명 작성"
git push
```

---

## 6. 원격 변경 가져오기 — `pull` (prd §7)

로컬이 깨끗하고 push가 끝난 상태에서 수행한다.

```bash
git status
```

1. GitHub `prompt-manager` 저장소에서 `README.md` 를 열고 연필(Edit) 아이콘으로 맨 아래에 한 줄 추가한다.
   (예: `문의: GitHub Issues 를 이용해 주세요.`) → *Commit changes*
2. 로컬로 반영한다.

```bash
git pull
git log --oneline -3
tail -3 README.md
```

웹에서 만든 커밋이 로그 맨 위에 보이면 성공이다.

---

## 7. 수용 기준 검증 T1~T10 (prd §10)

모두 `prompt-manager` 폴더에서 실행한다. 출력에서 아래 **기대 결과** 를 확인한다.

| # | 명령 | 기대 결과 |
|---|---|---|
| T1 | `printf '2\n0\n' \| python prompt_manager.py` | 메뉴 출력, 목록에 `총 5개의 프롬프트` (3개 이상) |
| T2 | `printf '9\nabc\n\n0\n' \| python prompt_manager.py` | `올바른 번호를 입력하세요.` 3회 후 메뉴 재출력 |
| T3 | `printf '1\n   \n제목\n내용\n1\n0\n' \| python prompt_manager.py` | `값을 입력해야 합니다.` 후 추가 완료 |
| T4 | `printf '1\n제목\n내용\n1\n2\n0\n' \| python prompt_manager.py` | 목록 6번에 `[텍스트 생성] 제목` (⭐ 없음) |
| T5 | `printf '1\n제목\n내용\n7\n코딩\n3\n7\n0\n' \| python prompt_manager.py` | 카테고리 목록에 `7) 코딩`, 조회 결과에 `[코딩] 제목` |
| T6 | `printf '4\n블로그\n4\n없는단어\n0\n' \| python prompt_manager.py` | 결과 1건 / `검색 결과가 없습니다.` |
| T7 | `printf '5\n1\n5\n999\n0\n' \| python prompt_manager.py` | 전체 내용 출력 / `1~5 사이의 번호를 입력하세요.` |
| T8 | `printf '6\n2\n6\n2\n0\n' \| python prompt_manager.py` | `추가했습니다!` → `해제했습니다!` |
| T9 | `printf '7\n0\n' \| python prompt_manager.py` | ⭐ 항목(블로그 글 작성 도우미)만 출력 |
| T10 | `printf '0\n' \| python prompt_manager.py` | `프로그램을 종료합니다.` 후 정상 종료 |

> 이모지·한글이 깨지면 `export PYTHONUTF8=1` 을 먼저 실행한다. (PowerShell: `$env:PYTHONUTF8=1`)
> Windows PowerShell에서는 `printf` 대신 `"9`nabc`n`n0`n" | python prompt_manager.py` 형식을 쓴다.

---

## 8. 제출물 준비 (prd §11)

### 8-1. 최종 상태 확인

```bash
git status
git log --oneline --graph
git branch -a
git remote -v
```

체크리스트:

- [ ] `git status` → `nothing to commit, working tree clean`
- [ ] 커밋 10개 이상 (병합 커밋 포함 14개 이상: #1~#13 + 웹 수정 1개)
- [ ] 그래프에 `|\` … `|/` 형태의 브랜치·병합 기록
- [ ] GitHub *Commits* 화면에서 동일한 이력 확인

기대 출력 형태 (해시는 실제와 다름):

```text
* a1b2c3d Update README.md
* d4e5f6a docs: README 기능 목록·실행 방법·카테고리 설명 작성
* 0718293 feat: 즐겨찾기 추가/해제 및 목록 기능
* 3a4b5c6 feat: 프롬프트 상세 보기 기능
* 7d8e9f0 feat: 프롬프트 검색 기능
* 1a2b3c4 feat: 카테고리별 조회 기능
*   5d6e7f8 Merge branch 'feature/prompt-list'
|\
| * 9a0b1c2 feat: 프롬프트 목록 기능
|/
* 3d4e5f6 feat: 프롬프트 추가 기능
* 7a8b9c0 feat: 입력 검증 헬퍼 함수 추가
* 1d2e3f4 feat: 이전 미션 프롬프트 기본 데이터 등록
* 5a6b7c8 feat: 잘못된 메뉴 입력 처리
* 9d0e1f2 feat: 메뉴 출력 및 메인 루프, 종료 기능
* 3a4b5c6 chore: 프로젝트 초기화 (.gitignore, README 제목)
```

### 8-2. 제출물 목록

| 제출물 | 준비 방법 |
|---|---|
| GitHub 저장소 URL | `https://github.com/andrewjung376/prompt-manager` |
| ① 개발 환경 스크린샷 | 1장에서 캡처 (VSCode Python 확장, Python 버전, Git 설정) |
| ② 프로그램 실행 스크린샷 | `python prompt_manager.py` 실행 후 메뉴, 프롬프트 추가, 목록, 검색이 보이게 캡처 |
| ③ `git log --oneline --graph` 스크린샷 | 8-1의 출력 캡처 (병합 갈래가 보이도록 터미널 창을 충분히 넓게) |

캡처는 `Win + Shift + S` 를 사용한다.

### 8-3. (선택) 스크린샷을 저장소에 함께 올리기

```bash
mkdir -p docs/screenshots
# 캡처 이미지를 docs/screenshots/ 에 저장한 뒤
git add docs/screenshots
git commit -m "docs: 제출용 스크린샷 추가"
git push
```

---

## 9. 명령어 요약 (project.md 과제 목표)

| 명령어 | 하는 일 | 사용한 곳 |
|---|---|---|
| `git init` | 현재 폴더를 Git 저장소로 초기화(`.git/` 생성) | 3장 |
| `git add` | 변경 파일을 스테이징 영역에 올림 | 3·5장 |
| `git commit` | 스테이징된 변경을 하나의 이력(스냅샷)으로 저장 | 3·5장 |
| `git push` | 로컬 커밋을 원격 저장소(GitHub)에 업로드 | 3·5장 |
| `git pull` | 원격 변경을 내려받아 현재 브랜치에 병합 | 6장 |
| `git checkout` | 브랜치 이동, `-b` 로 새 브랜치 생성 후 이동 | 5장 #7, #8 |
| `git clone` | 원격 저장소 전체(파일+이력)를 로컬에 복제 | 4장 |
| `git merge` | 다른 브랜치의 변경을 현재 브랜치에 합침 | 5장 #8 |

**Git이 필요한 이유:** 변경 이력을 기록해 언제든 이전 상태로 되돌릴 수 있고, 브랜치로 기능을 독립적으로 개발한 뒤 안전하게 합칠 수 있으며, GitHub로 코드를 백업·공유·협업할 수 있다.

---

## 10. 문제 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| `fatal: not a git repository` | 프로젝트 폴더 밖에서 실행 | `cd /c/dev/git/andrewjung376/prompt-manager` |
| `error: remote origin already exists` | 원격 중복 등록 | `git remote set-url origin <URL>` |
| `! [rejected] main -> main (fetch first)` | 원격에 로컬에 없는 커밋 존재 | `git pull` 후 다시 `git push` |
| `Author identity unknown` | 사용자 정보 미설정 | 1장의 `git config` 실행 |
| push 시 인증 실패 | GitHub 로그인 필요 | VSCode GitHub 로그인 또는 `gh auth login` |
| 병합 후 그래프에 갈래가 안 보임 | fast-forward 병합 | `--no-ff` 옵션 사용 |
| `UnicodeEncodeError`, 이모지 깨짐 | 콘솔 인코딩 | `export PYTHONUTF8=1` 또는 `chcp 65001` |
| `NameError: name 'xxx' is not defined` | 함수 붙여넣기 누락 또는 `main()` 분기만 추가 | 해당 단계의 함수를 `def main():` 위에 붙여넣었는지 확인 |
| 커밋 후 `git push` 시 브랜치 upstream 없음 | 새 브랜치 첫 push | `git push -u origin <브랜치명>` |
