# BOJ CLI Tools (`bojtools`)
- 백준([Baekjoon Online Judge](https://www.acmicpc.net/)) + [Solved.ac](https://solved.ac/) 을 위한 커맨드라인 도구입니다.

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
- baekjoon, solved.ac에 자동으로 로그인합니다.
- 브라우저가 필요합니다.  (chromium, google-chrome, ...)
- login 정보를 입력하면 브라우저가 실행 되며 자동 login 됩니다.
- login cookie는 `state_path`에 저장됩니다.
  - Default: `~/.boj/state.json`

```sh
boj login
...
Username: userid
Password: 
```


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
- `-f' : 문제 상태 강제 갱신 (AC/WA)

예시:
```sh
boj p
boj p <번호>
boj pick <번호>
boj p -f <번호>
```

## `boj random`
- [Solved.ac](https://solved.ac/)의 특정 난이도(Gold, Silver, ...) 문제를 랜덤으로 선택합니다.
- `-s' : 최소 풀이 인원
- `-l`: 문제 목록 출력
- 난이도 (b, s, g, p, d, r, b1, g1, ...)
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
- config.toml의 기본 template에서 복사됩니다. (Default: ~/.boj/template.cpp)

예시:
```sh
cd <번호>
boj g
boj generate <번호>
```

## `boj test`
- 코드를 compile해서 test case의 intput, output으로 test 합니다.
- gcc 등의 compiler 설치가 필요합니다.

예시:
```sh
boj t
boj test <번호>
boj test <번호> -i <파일>
```

## `boj submit`
- 작성한 코드를 자동으로 제출합니다.
- 문제 제출은 Cloudflare Turnstile 때문에 브라우저가 필수 입니다.

예시:
```sh
boj s
boj submit <번호>
boj submit <번호> -i <파일>
```

## `boj solution`
- 통과한 문제의 다른 코드를 확인합니다.
- 본인이 통과(AC)한 문제만 가능합니다.

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

## 환경설정 경로
### Linux
- ~/.boj/config.toml
