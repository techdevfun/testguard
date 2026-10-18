# Contributing

Bug reports and small, focused PRs are welcome.

- Keep the tool zero-dependency (Python standard library only).
- Every new check needs a fixture case in `tests/fixtures/` plus a test
  in `tests/test_testguard.py` proving it fires on the bad pattern and
  stays silent on the clean pattern.
- Run `python -m unittest discover -s tests` before opening a PR.
- Do not use this tool to shame anyone — a finding is a starting point
  for a conversation, not proof of bad intent. Retries and skips are
  sometimes legitimate; the report says *where to look*, not *who to blame*.
