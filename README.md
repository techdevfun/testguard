# testguard — catch tests that lie

CI is green. The bug shipped anyway. How?

Because a test suite can be green without testing anything. An AI
coding agent under pressure — or a tired human at 11pm — can make
failing tests pass without fixing the code:

- delete the failing test,
- wrap the assertion in a retry loop (`for _ in range(5): try: assert ...`),
- swallow the `AssertionError` in `try/except: pass`,
- `@pytest.mark.skip` the flaky test,
- `assert True`,
- `time.sleep(2)` and hope the race goes away.

testguard scans your test files (Python + JavaScript/TypeScript) for
exactly those patterns and reports each one with file, line and
evidence. It can also scan a `git diff`, so a PR that weakens tests
gets flagged before it merges.

Zero dependencies. Python 3.9+. Runs in under a second on a typical repo.

## Demo

```text
$ python -m testguard tests/fixtures/py_cheating.py
testguard: 10 suspicious pattern(s) found:

tests/fixtures/py_cheating.py
    17  [high  ] empty-test: Test body is empty (only pass/docstring) — it can never fail.
    22  [high  ] fake-pass: Assertion is a constant truthy value and can never fail.
    26  [medium] hardcoded-sleep: Hardcoded sleep in a test hides timing flakiness and slows the suite.
    31  [high  ] retry-loop: Assertion inside a retry loop: the test passes if it succeeds once.
    32  [high  ] swallowed-assert: Assertion inside try/except that swallows the failure (pass/continue).
    47  [low   ] skipped-test: Test is skipped and never runs.
    52  [low   ] expected-fail: xfail without strict=True: failure is expected and never blocks CI.
    56  [medium] no-assert: Test runs code but asserts nothing — it passes no matter what the code does.
    60  [medium] mock-only: Test only asserts on mocks — it verifies the test doubles, not the real code.

$ python -m testguard tests/fixtures/py_clean.py
testguard: clean — no suspicious test patterns found.
```

Try it on the realistic examples in this repo:

```text
$ python -m testguard examples/cheating-demo   # exit 1, 5 findings
$ python -m testguard examples/clean-demo      # exit 0, clean
```

## Install

```bash
git clone https://github.com/techdevfun/testguard
cd testguard
python3 -m testguard tests/          # no install needed — stdlib only
```

Or install the command:

```bash
pip install .
testguard tests/
```

## Usage

```bash
# Scan a directory (default: current directory)
testguard tests/

# JSON output for CI dashboards
testguard tests/ --format json

# Only fail the build on high-severity findings
testguard tests/ --fail-on high

# Never fail (report only)
testguard tests/ --fail-on none

# Scan what changed vs HEAD — catches tests weakened in a PR
testguard --diff HEAD
testguard --diff main
```

Exit codes: `0` clean (or below threshold), `1` findings at/above
`--fail-on`, `2` usage error (missing path, git failure).

## What it checks

| Check | Severity | Meaning |
|---|---|---|
| `empty-test` | high | Test body is only `pass` / docstring — can never fail |
| `fake-pass` | high | `assert True`, `expect(true).toBe(true)` — can never fail |
| `retry-loop` | high | Assertion inside a retry loop — passes if it succeeds once |
| `swallowed-assert` | high | Assertion in `try/except: pass` — failure is discarded |
| `deleted-test` | high | (diff mode) a test was deleted or renamed |
| `removed-assert` | high | (diff mode) assertion removed, no replacement added |
| `added-fake-pass` | high | (diff mode) a never-failing assertion was added |
| `focused-test` | high | `.only()` — runs one test, silently skips the rest |
| `no-assert` | medium | Test runs code but asserts nothing |
| `hardcoded-sleep` | medium | `time.sleep` / `setTimeout` hides timing flakiness |
| `mock-only` | medium | Test asserts only on mocks, not on real behaviour |
| `added-skip` / `added-sleep` | medium | (diff mode) skip / sleep added in this change |
| `skipped-test` | low | `@pytest.mark.skip`, `test.skip`, `.todo` — never runs |
| `expected-fail` | low | `xfail` without `strict=True` — failure never blocks CI |
| `parse-error` | low | Test file does not parse |

Python checks run on the real AST, not regexes, so formatting tricks
don't hide a fake pass — but a `sleep` in a *helper* (not a test) is
left alone. JS/TS checks are line-based and cover Jest, Vitest, Mocha,
Bun and Node's built-in runner.

## CI gate

```yaml
- name: Fail on manipulated tests
  run: python -m testguard tests/ --fail-on medium
```

Or copy `examples/ci/check.sh` into your pipeline. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the check-development workflow.

## Honesty notes

testguard reports *patterns*, not guilt. A retry loop around a genuinely
flaky third-party call, a skipped test with a linked issue, or a mock-heavy
test for a thin adapter can all be legitimate. Treat each finding as
"look here and decide", not "this code is cheating". False positives are
possible — that's why `--fail-on` exists, and why the report always shows
its evidence.

## Roadmap

- TypeScript-aware parsing (tsc AST) instead of line scanning for JS/TS.
- Go / Rust test files.
- `--baseline` file to silence known-accepted findings.
- Suggested fix hints per finding.

## License

MIT — see [LICENSE](LICENSE).
