# BOJ CLI Tools (`bojtools`)
- A command-line tool for [Baekjoon Online Judge](https://www.acmicpc.net/) + [Solved.ac](https://solved.ac/).

[한국어](./README.md) · [English](./README.en.md)

## Key Features
- Pick problems / view problem info (`pick`, `info`)
- Random/class-based recommendations from Solved.ac (`random`, `class`)
- Generate code files from templates (`generate`)
- Run local tests (`test`)
- Browser-based login/submission (`login`, `submit`)
- View accepted solutions (`solution`)

## Installation

### pip
```sh
pip3 install bojtools
```

### uv
```sh
uv pip install bojtools
```

## `boj init`
- Initializes the configuration file.

```sh
boj init
```
Generated file:
- `~/.boj/config.toml`

## `boj login`
- Automatically logs in to Baekjoon and Solved.ac.
- A browser is required (chromium, google-chrome, ...).
- After entering credentials, a browser opens and performs auto-login.
- Login cookies are saved to `state_path`.
  - Default: `~/.boj/state.json`

```sh
boj login
...
Username: userid
Password:
```

## Directory Structure
- If `code_dir` in *config.toml* is `~/code`, it is structured like this. (default: `~/boj/code`)
- Test cases and code files are stored per problem number.
- Names like `1000.cpp`, `1000.dfs.cpp` are allowed, but only one code file should exist.

```
code
├── 1000
│   ├── 1000.cpp
│   ├── ans1.txt
│   └── in1.txt
├── 1006
│   ├── 1006.cpp
│   ├── ans1.txt
│   └── in1.txt
```

## `boj pick`
- Picks a problem.
- If no number is given, shows information for the current directory.
- `-f`: force-refresh problem status (AC/WA)

Examples:
```sh
boj p
boj p <number>
boj pick <number>
boj p -f <number>
```

## `boj random`
- Randomly picks a problem at a target difficulty (Gold, Silver, ...) from [Solved.ac](https://solved.ac/).
- `-s`: minimum number of solved users
- `-l`: print problem list
- Difficulty levels (`b`, `s`, `g`, `p`, `d`, `r`, `b1`, `g1`, ...)
  - b: Bronze
  - s: Silver
  - g: Gold
  - p: Platinum
  - d: Diamond
  - r: Ruby

Examples:
```sh
# Pick Bronze problems
boj r b1 b5
boj random --silver

# Pick randomly between Gold1 and Gold5
boj r -s 1000 g1 g5

# Pick problems solved by at least 1000 users, from Silver2 to Gold3
boj r -s 1000 s2 g3
```

## `boj generate`
- Generates starter code from a template.
- Copied from the template in `config.toml`. (Default: `~/.boj/template.cpp`)

Examples:
```sh
cd <number>
boj g
boj generate <number>
```

## `boj test`
- Compiles code and tests with testcase input/output.
- A compiler such as gcc is required.

Examples:
```sh
boj t
boj test <number>
boj test <number> -i <file>
```

## `boj submit`
- Automatically submits your code.
- A browser is required for submission due to Cloudflare Turnstile.

Examples:
```sh
boj s
boj submit <number>
boj submit <number> -i <file>
```

## `boj solution`
- Views other accepted solutions for a problem.
- Only available for problems you solved with AC.

Examples:
```sh
boj q
boj solution <number>
```

## `boj class <level>`
- Randomly picks a problem from solved.ac Class.
- `-e`: essential problems only
- `-l`: print problem list

Examples:
```sh
# Pick an unsolved problem from Solved.ac Class 6
boj c 6
boj class <Level>
```

## `boj info`
- Prints basic problem info (title, URL, etc.).
- `-l`: print difficulty level

Examples:
```sh
boj i
boj info <number>

# Print difficulty (Silver, Gold, Platinum, ...)
boj i -l <number>
```

## Configuration Path
### Linux
- `~/.boj/config.toml`
