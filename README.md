# BOJ CLI Tools (`bojtools`)
- 백준([Baekjoon Online Judge](https://www.acmicpc.net/)) + [Solved.ac](https://solved.ac/) 을 위한 커맨드라인 도구입니다.

[한국어](./README.md) · [English](./README.en.md)

## 주요 기능
- 문제 선택/정보 조회 (`pick`, `info`)
- Solved.ac 기반 랜덤/클래스 문제 추천 (`random`, `class`)
- 템플릿 기반 코드 파일 생성 (`generate`)
- 로컬 테스트 실행 (`test`)
- 브라우저 기반 로그인/제출 (`login`, `submit`)
- 통과한 문제의 풀이 확인 (`solution`)

## 설치

### pip
```sh
pip3 install bojtools
```

### uv
```sh
uv pip install bojtools
```

## `boj init`
- 설정파일을 초기화합니다.

```sh
boj init
```
생성 파일:
- `~/.boj/config.toml`

## `boj login`
- solved.ac의 "BOJ로 로그인"을 통해 baekjoon, solved.ac에 로그인합니다.
- Patchright가 설정의 `browser` 또는 설치된 Chrome/Chromium을 실행합니다. 브라우저를 찾지 못하면 `patchright install chromium`으로 Chromium을 설치하세요.
- BOJ 계정 정보를 입력하면 브라우저가 실행됩니다. 브라우저에서 추가 인증이 표시되면 완료해 주세요.
- "BOJ로 로그인" 버튼이 준비되면 자동 클릭하고, BOJ 로그인 후 SSO 승인 화면의 "로그인" 링크나 버튼도 자동 클릭합니다.
- 브라우저 상태 파일이 없으면 `state_path`의 로그인 쿠키를 복원합니다. 세션이 만료됐다면 `boj login`을 실행하세요.

```sh
boj login
...
Username: userid
Password: 
```

## solved.ac API 설정

```toml
solved_handle = "<solved.ac 사용자명>"
```

- `solved_handle`은 `random`과 `class`에서 이미 푼 문제를 제외하는 데 사용합니다. 로그인할 때 기본값으로 BOJ 아이디를 저장하므로, solved.ac 핸들이 다르면 이 값을 설정해 주세요. `class --all`과 `info --level`에는 핸들이 필요하지 않습니다.
- `boj info --level`은 캐시가 없으면 solved.ac 문제 상세 페이지에서 난이도를 읽습니다. 해당 페이지에서 난이도를 읽지 못해도 BOJ 문제 정보는 표시합니다.


## 디렉토리 구조
- *config.toml* 의 `code_dir`이 `~/code` 인 경우 다음과 같이 구성됩니다. (default: ~/boj/code)
- 각각의 문제 번호에 test case와 code file이 저장됩니다.
- 1000.cpp, 1000.dfs.cpp 등도 가능하지만 하나의 파일만 있어야 합니다.

```
code
├── 1000
│   ├── 1000.cpp
│   ├── ans1.txt
│   └── in1.txt
├── 1006
│   ├── 1006.cpp
│   ├── ans1.txt
│   └── in1.txt
```

## `boj pick`
- 문제를 선택합니다.
- 번호를 지정하지 않으면 현재 디렉토리의 정보를 표시합니다.
- 문제 설명의 TeX 수식(`\(...\)`, `\[...\]`)은 터미널 출력 시 텍스트로 변환합니다. 해석할 수 없는 수식은 원문 그대로 표시합니다.
- `-f`: 문제 상태 강제 갱신 (AC/WA)

예시:
```sh
boj p
boj p <번호>
boj pick <번호>
boj p -f <번호>
```

## `boj random`
- [Solved.ac](https://solved.ac/)의 특정 난이도(Gold, Silver, ...) 문제를 랜덤으로 선택합니다.
- `-s`: 최소 풀이 인원
- `-l`: 문제 목록 출력
- 난이도 (`b`, `s`, `g`, `p`, `d`, `r`, `b1`, `g1`, ...)
  - b: Bronze
  - s: Silver
  - g: Gold
  - p: Platinum
  - d: Diamond
  - r: Ruby

예시:
```sh
# Bronze 문제 출력
boj r b1 b5
boj random --silver

# Gold1 에서 Gold5 까지 문제 중 랜덤 선택
boj r -s 1000 g1 g5

# Silver2 에서 Gold3 까지 1000명 이상 푼 문제만 선택
boj r -s 1000 s2 g3
```

## `boj generate`
- 기본적인 template code를 생성합니다.
- `config.toml`의 `template` 파일을 복사합니다. 기본값은 `~/.boj/template.cpp`입니다.
- `language = "rs"`처럼 확장자를 설정하면 같은 디렉터리에서 `template.rs`를 읽어 `<번호>.rs`를 생성합니다. `java`, `go`, `cpp`, `py`도 같은 방식으로 선택할 수 있습니다. 사용할 템플릿 파일은 직접 준비하세요.

예시:
```sh
cd <번호>
boj g
boj generate <번호>
```

## `boj test`
- 코드를 compile해서 test case의 intput, output으로 test 합니다.
- gcc 등의 compiler 설치가 필요합니다.
- 문제 번호를 지정하면 `code_dir/<번호>`를 기준으로 예제 입출력과 소스를 찾습니다. `-i`를 지정하면 해당 소스 파일을 사용합니다.

예시:
```sh
boj t
boj test <번호>
boj test <번호> -i <파일>
```

## `boj submit`
- 작성한 코드를 자동으로 제출합니다.
- 소스 확장자에 맞춰 제출 언어를 선택합니다. 기본 설정은 C++17, Python 3, Rust 2021, Java 11, Go를 지원합니다. Java 제출 코드는 `Main` 클래스를 사용하세요.
- 문제 번호를 지정하면 `code_dir/<번호>`를 기준으로 제출할 소스를 찾습니다. `-i`를 지정하면 해당 소스 파일을 사용합니다.
- 문제 제출은 Cloudflare Turnstile 때문에 브라우저가 필수 입니다.
- 브라우저에서 Cloudflare의 체크박스가 뜨면 클릭하시면 submit 됩니다.
- 제출 후 채점 결과를 최대 60초 동안 확인합니다. 결과를 터미널에 표시한 뒤 10초 후 브라우저를 닫습니다. 제출 오류가 표시되거나 제한 시간 안에 결과를 읽지 못하면 직접 확인할 수 있도록 탭을 열어 둡니다.

예시:
```sh
boj s
boj submit <번호>
boj submit <번호> -i <파일>
```

## `boj solution`
- 통과한 문제의 다른 코드를 확인합니다.
- 본인이 통과(AC)한 문제만 가능합니다.
- `language` 설정의 확장자에 해당하는 BOJ 언어로 조회합니다. 설정이 비어 있으면 등록된 템플릿 확장자를 참고하며, 기본 C++ 템플릿은 전체 C++ 풀이를 조회합니다.

예시:
```sh
boj q
boj solution <번호>
```

## `boj class <level>`
- solved.ac의 Class에서 랜덤하게 문제를 선택합니다.
- `-e`: essential 문제
- `-l`: 문제 목록 출력

예시:
```
# Solved.ac Class6 에서 미해결 문제 선택
boj c 6
boj class <Level>
```

## `boj info`
- 문제의 제목, url등 기본 정보를 출력합니다.
- `-l`: 난이도 출력

예시:
```sh
boj i
boj info <번호>

# 난이도 출력 (Silver, Gold, Platinum, ...)
boj i -l <번호>
```

## `boj archive <시작 번호> <끝 번호>`
- 새로 가져온 문제의 HTML을 `code_dir/<번호>.raw`에 UTF-8로 저장합니다.

## 개발 테스트

프로젝트와 pytest를 설치한 환경에서 저장소 루트에서 실행합니다. 테스트는 임시 디렉터리와 모의 HTTP·브라우저를 사용합니다.

```sh
pytest
```

## 환경설정 경로
### Linux
- ~/.boj/config.toml
