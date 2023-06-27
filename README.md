# BOJ([Baekjoon Online Judge](https://www.acmicpc.net/)) CLI tools
백준 & Solved.ac Command-line 도구

# 설치
```sh
pip3 install bojtools
```

# 사용법
## 문제 선택
```sh
boj pick <번호>
boj p <번호>
```

## 랜덤 문제
[Solved.ac](https://solved.ac/) 에서 특정 난이도(Gold, Silver, ...) 문제를 랜덤으로 가져옴.

```sh
boj random --silver
boj r -s
```

## 파일 생성
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

## 다른 솔루션 보기
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
- [ ] Baekjoon workbook
- [x] Compile and test
- [x] Submit a code
- [ ] Extract cookies
- [x] Text width
- [x] View other solution
- [x] Support python
- [ ] Support multi-platform
