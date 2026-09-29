# CLI 실행 가이드: GitHub 저장소 생성부터 브랜치 병합까지

> 근거 문서: [project.md](../project.md), [prd.md](prd.md)
>
> 이 문서는 과제 중 **GitHub 새 저장소 생성, `git init`, 10개 이상의 기능 단위 커밋, 브랜치 생성·병합** 을 수행하는 명령을 순서대로 정리한 실행 가이드다.
> 명령은 Windows의 Git Bash 또는 VSCode 통합 터미널(PowerShell) 기준이며, 두 셸에서 동일하게 동작한다.

---

## 0. 사전 준비 (1회)

```bash
python --version
git --version
git config --global user.name "andrewjung376"
git config --global user.email "<GitHub 계정 이메일>"
git config --global init.defaultBranch main
git config --global --list
```

| 확인 항목 | 기대 결과 |
|---|---|
| `python --version` | `Python 3.10` 이상 |
| `git --version` | `git version 2.x` |
| `git config --global --list` | `user.name`, `user.email`, `init.defaultbranch=main` 표시 |

VSCode 좌측 하단 **계정(Accounts)** 아이콘 → *Sign in with GitHub* 로 로그인해 두면 `push` 시 인증 창이 자동으로 처리된다.

---

## 1. GitHub 새 저장소 생성

### 방법 A: 웹 브라우저

1. <https://github.com/new> 접속
2. Repository name: `prompt-manager`
3. Public 선택
4. **Add a README / .gitignore / license는 모두 체크 해제** (로컬에서 만들어 첫 push 충돌을 피한다)
5. *Create repository* 클릭 → 저장소 URL 복사: `https://github.com/andrewjung376/prompt-manager.git`

### 방법 B: GitHub CLI (`gh`가 설치된 경우)

```bash
gh auth login
gh repo create prompt-manager --public
```

---

## 2. 로컬 저장소 초기화 (`init`) 와 첫 커밋 (`add`, `commit`, `push`)

> 저장소가 중첩되지 않도록 **기존 `ai-codyssey` 저장소 밖**에 프로젝트 폴더를 만든다.

```bash
cd C:/dev/git/andrewjung376
mkdir prompt-manager
cd prompt-manager
git init
```

`git init` 결과로 `.git/` 폴더가 생성되고 `main` 브랜치에서 시작한다.

VSCode로 폴더를 열고(`code .`) 다음 두 파일을 작성한다.

**`.gitignore`**

```text
__pycache__/
*.pyc
.venv/
.vscode/
*.json
```

**`README.md`**

```markdown
# 나만의 프롬프트 관리 프로그램
```

원격 저장소를 연결하고 첫 커밋을 올린다.

```bash
git add .gitignore README.md
git commit -m "chore: 프로젝트 초기화 (.gitignore, README 제목)"
git remote add origin https://github.com/andrewjung376/prompt-manager.git
git remote -v
git push -u origin main
```

`-u` 옵션으로 upstream이 설정되므로 이후에는 `git push` 만 입력하면 된다.

---

## 3. 샘플 저장소 내려받기 (`clone`)

프로젝트 폴더 **밖**에서 실행한다.

```bash
cd C:/dev/git/andrewjung376
git clone https://github.com/octocat/Spoon-Knife.git
cd Spoon-Knife
ls
git log --oneline -5
cd ..
rm -rf Spoon-Knife
```

폴더 구조와 커밋 로그를 확인한 뒤 삭제한다. (PowerShell에서는 마지막 줄 대신 `Remove-Item -Recurse -Force Spoon-Knife`)

---

## 4. 기능 단위 커밋 (13개)

모든 작업은 `prompt-manager` 폴더에서 진행한다. 각 단계는 **① 코드 작성 → ② 실행 확인 → ③ 커밋 → ④ push** 순서를 따른다.

```bash
cd C:/dev/git/andrewjung376/prompt-manager
python prompt_manager.py
git status
```

| # | 브랜치 | 작업 내용 (prd.md 기준) | 커밋 메시지 |
|---|---|---|---|
| 1 | main | `.gitignore`, README 제목 (2장에서 완료) | `chore: 프로젝트 초기화 (.gitignore, README 제목)` |
| 2 | main | `main()`, `show_menu()`, 0번 종료 | `feat: 메뉴 출력 및 메인 루프, 종료 기능` |
| 3 | main | 잘못된 번호·문자 입력 안내 | `feat: 잘못된 메뉴 입력 처리` |
| 4 | main | `CATEGORIES`, `DEFAULT_PROMPTS` 3개 이상 | `feat: 이전 미션 프롬프트 기본 데이터 등록` |
| 5 | main | `input_non_empty()`, `input_number()`, `select_category()` | `feat: 입력 검증 헬퍼 함수 추가` |
| 6 | main | `add_prompt()` (F2) | `feat: 프롬프트 추가 기능` |
| 7 | **feature/prompt-list** | `show_list()`, `format_prompt_line()` (F3) | `feat: 프롬프트 목록 기능` |
| 8 | main | 브랜치 병합 (5장 참고) | `Merge branch 'feature/prompt-list'` |
| 9 | main | `show_by_category()` (F4) | `feat: 카테고리별 조회 기능` |
| 10 | main | `search_prompt()` (F5) | `feat: 프롬프트 검색 기능` |
| 11 | main | `show_detail()` (F6) | `feat: 프롬프트 상세 보기 기능` |
| 12 | main | `toggle_favorite()`, `show_favorites()` (F7, F8) | `feat: 즐겨찾기 추가/해제 및 목록 기능` |
| 13 | main | README 설명·실행 방법·기능·카테고리 | `docs: README 기능 목록·실행 방법·카테고리 설명 작성` |

### 커밋 2~6 (main 브랜치)

단계마다 아래 3줄을 반복한다. (예: 2번)

```bash
git add prompt_manager.py
git commit -m "feat: 메뉴 출력 및 메인 루프, 종료 기능"
git push
```

3~6번도 같은 방식으로 표의 커밋 메시지만 바꿔 실행한다.

### 커밋 9~13 (병합 후 main 브랜치)

```bash
git add prompt_manager.py
git commit -m "feat: 카테고리별 조회 기능"
git push
```

13번은 README 커밋이다.

```bash
git add README.md
git commit -m "docs: README 기능 목록·실행 방법·카테고리 설명 작성"
git push
```

> **좋은 커밋 규칙:** 한 커밋에는 한 기능만 담는다. 메시지는 `타입: 무엇을 했는지` 형식(`feat`, `fix`, `docs`, `chore`)으로 변경 의도를 설명한다.

---

## 5. 브랜치 생성과 병합 (`checkout`, `merge`)

커밋 6까지 끝난 뒤 목록 기능(F3)을 별도 브랜치에서 작업한다.

### 5-1. 브랜치 생성·이동

```bash
git checkout -b feature/prompt-list
git branch
```

`git branch` 결과에서 `* feature/prompt-list` 에 별표가 있으면 성공이다.

### 5-2. 브랜치에서 작업·커밋 (커밋 7)

`show_list()` 를 구현하고 실행 확인 후 커밋한다.

```bash
git add prompt_manager.py
git commit -m "feat: 프롬프트 목록 기능"
git push -u origin feature/prompt-list
```

### 5-3. main으로 돌아와 병합 (커밋 8)

```bash
git checkout main
git merge --no-ff feature/prompt-list -m "Merge branch 'feature/prompt-list'"
git push
```

- `--no-ff` 를 사용하면 fast-forward 대신 **병합 커밋**이 생성되어 `git log --graph` 에 브랜치 갈래가 남는다.
- 병합 후 브랜치 정리(선택):

```bash
git branch -d feature/prompt-list
git push origin --delete feature/prompt-list
```

### 5-4. 충돌이 발생한 경우

```bash
git status
```

`both modified` 로 표시된 파일을 VSCode에서 열어 `<<<<<<<`, `=======`, `>>>>>>>` 구간을 정리한 뒤 다음을 실행한다.

```bash
git add prompt_manager.py
git commit
```

---

## 6. 원격 변경 가져오기 (`pull`)

1. GitHub 웹에서 `README.md` 를 열고 연필(Edit) 아이콘으로 한 줄 수정 → *Commit changes*
2. 로컬에서 반영한다.

```bash
git pull
git log --oneline -3
```

웹에서 만든 커밋이 로컬 로그 맨 위에 보이면 성공이다.

> 로컬에 push하지 않은 커밋이 있는 상태에서 웹 수정을 하면 `pull` 시 병합이 발생할 수 있다. 가능하면 `git status` 가 깨끗한 상태에서 수행한다.

---

## 7. 결과 확인 (제출 스크린샷)

```bash
git log --oneline --graph
```

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

체크리스트:

- [ ] 커밋 10개 이상 (병합 커밋 제외 12개 + 병합 1개 + pull 1개)
- [ ] `|\` … `|/` 형태의 브랜치·병합 기록 존재
- [ ] GitHub 저장소 *Commits* 화면에서도 동일한 이력 확인
- [ ] `git status` → `nothing to commit, working tree clean`

---

## 8. 명령어 요약 (과제 목표: 각 명령 설명)

| 명령어 | 하는 일 | 이 과제에서 사용한 곳 |
|---|---|---|
| `git init` | 현재 폴더를 Git 저장소로 초기화(`.git/` 생성) | 2장 |
| `git add` | 변경 파일을 스테이징 영역에 올림 | 2·4·5장 |
| `git commit` | 스테이징된 변경을 하나의 이력(스냅샷)으로 저장 | 2·4·5장 |
| `git push` | 로컬 커밋을 원격 저장소(GitHub)에 업로드 | 2·4·5장 |
| `git pull` | 원격 저장소의 변경을 내려받아 현재 브랜치에 병합 | 6장 |
| `git checkout` | 브랜치 이동, `-b` 로 새 브랜치 생성 후 이동 | 5장 |
| `git clone` | 원격 저장소 전체(파일+이력)를 로컬에 복제 | 3장 |
| `git merge` | 다른 브랜치의 변경을 현재 브랜치에 합침 | 5장 |

**Git이 필요한 이유:** 변경 이력을 기록해 언제든 이전 상태로 되돌릴 수 있고, 브랜치로 기능을 독립적으로 개발한 뒤 안전하게 합칠 수 있으며, GitHub를 통해 코드를 백업·공유·협업할 수 있다.

---

## 9. 문제 해결

| 증상 | 원인 | 해결 |
|---|---|---|
| `fatal: not a git repository` | 프로젝트 폴더 밖에서 실행 | `cd` 로 `prompt-manager` 이동 |
| `error: remote origin already exists` | 원격 중복 등록 | `git remote set-url origin <URL>` |
| `! [rejected] main -> main (fetch first)` | 원격에 로컬에 없는 커밋 존재 | `git pull` 후 다시 `git push` |
| `Author identity unknown` | 사용자 정보 미설정 | 0장의 `git config` 실행 |
| push 시 인증 실패 | GitHub 로그인 필요 | VSCode GitHub 로그인 또는 `gh auth login` |
| 병합 후 그래프에 갈래가 안 보임 | fast-forward 병합 | `--no-ff` 옵션 사용 |
