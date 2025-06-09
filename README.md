# BOJ([Baekjoon Online Judge](https://www.acmicpc.net/)) CLI tools
백준 & Solved.ac Command-line 도구

# 설치
```sh
pip3 install bojtools
```

# 사용법

## 초기화
```sh
boj init
```

## 로그인
```sh
boj login
...
Username: userid
Password: 
```

- 자동 로그인에 자동으로 체크 됩니다.

## 문제 선택
```sh
boj pick <번호>
boj p <번호>
# 문제 상태 (AC/WA) 강제 갱신
boj p -f
```

## 랜덤 문제 선택
[Solved.ac](https://solved.ac/) 에서 특정 난이도(Gold, Silver, ...) 문제를 랜덤으로 선택

```sh
boj random --silver
boj r -s
# Silver2 에서 Gold3 까지 1000명 이상 푼 문제만 list
boj r -s 1000 s2 g3
```

## Answer 파일 생성
- 설정된 기본 template에서 복사됩니다.
```sh
boj generate <번호>
boj g
```

## 테스트
```sh
boj test <번호> -i <파일>
boj test <번호>
boj t
```

## 문제 제출
```sh
boj submit <번호> -i <파일>
boj submit <번호>
boj s
```

## 문제 풀이 보기
- 제출되어 통과(AC)한 문제여야 표시 됩니다.
```sh
boj solution <번호>
boj q
```

## 문제 정보
```sh
boj generate <번호>
boj g
```

# 환경설정
## Linux
~/.boj/config.toml 파일 편집

[샘플 config.toml](https://github.com/zshchun/bojtools/blob/main/config.toml.example) 참조

# TODO
- [x] Solved.ac classes
- [x] Random pick from Solved.ac
- [x] Log in to Baekjoon and Solved.ac
- [ ] Baekjoon workbook
- [x] Compile and test
- [x] Submit a code
- [x] Extract cookies
- [x] Text width
- [x] View other solution
- [x] Support python
- [ ] Support multi-platform
- [ ] Improve guide documents
- [ ] Github action
- [x] Init command
- [ ] Edit command
- [ ] Open command
- [ ] Template command
- [ ] Migrate tomli to tomllib
