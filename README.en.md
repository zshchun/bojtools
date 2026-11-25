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
- Signs in to Baekjoon and solved.ac through solved.ac's "Sign in with BOJ" button.
- Patchright launches the configured `browser` or an installed Chrome/Chromium. If none is detected, install Chromium with `patchright install chromium`.
- Enter your BOJ credentials, then complete any additional verification shown in the browser.
- The app clicks "Sign in with BOJ" once its handler is ready, then automatically clicks the "Log in" link or button on the BOJ SSO approval page after BOJ sign-in.
- If the browser state file is absent, the app restores login cookies from `state_path`. If the session has expired, run `boj login`.

```sh
boj login
...
Username: userid
Password:
```

## solved.ac API setup

```toml
solved_handle = "<solved.ac username>"
```

- If the level is not cached, `boj info --level` reads it from the solved.ac problem page. If it cannot read the level, it still shows the BOJ problem information.

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
- TeX math (`$...$`, `$$...$$`, `\(...\)`, and `\[...\]`) in problem statements is converted to text for terminal display. Unsupported formulas are displayed as written.
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
- Copies the template set in `config.toml`, which defaults to `~/.boj/template.cpp`.
- Set `language = "rs"` to use a sibling `template.rs` and generate `<number>.rs`. The same rule applies to `java`, `go`, `cpp`, and `py`. Create the template file you want to use.

Examples:
```sh
cd <number>
boj g
boj generate <number>
```

## `boj test`
- Compiles code and tests with testcase input/output.
- A compiler such as gcc is required.
- With a problem number, sample files and source are found in `code_dir/<number>`. Use `-i` to specify a source file.

Examples:
```sh
boj t
boj test <number>
boj test <number> -i <file>
```

## `boj submit`
- Selects the submission language based on the source extension. The defaults support C++17, Python 3, Rust 2021, Java 11, and Go. Java submissions should use a `Main` class.
- Automatically submits your code.
- With a problem number, source is found in `code_dir/<number>`. Use `-i` to specify a source file.
- A browser is required for submission due to Cloudflare Turnstile.
- The CLI checks for the judging result for up to 60 seconds and closes the browser 10 seconds after printing it. If BOJ shows an error or no result arrives in time, the tab stays open for inspection.

Examples:
```sh
boj s
boj submit <number>
boj submit <number> -i <file>
```

## `boj solution`
- Views other accepted solutions for a problem.
- Filters by the BOJ language configured for the `language` extension. If unset, it uses the registered template extension, with the default C++ template showing all C++ solutions.
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

## `boj archive <start> <end>`
- Saves newly fetched problem HTML as UTF-8 in `code_dir/<number>.raw`.

## Running Tests

Run from the repository root in an environment with the project and pytest installed. Tests use temporary directories and mock HTTP and browser calls.

```sh
pytest
```

## Configuration Path
### Linux
- `~/.boj/config.toml`
