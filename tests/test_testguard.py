"""Tests for Python AST checks, JS checks, diff checks and the CLI."""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from testguard.core import analyze_diff, scan_path, scan_text  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _read(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


def _check_ids(findings):
    return {f.check_id for f in findings}


class PythonChecksTests(unittest.TestCase):
    def test_cheating_fixture_flags_every_pattern(self):
        findings = scan_text("py_cheating.py", _read("py_cheating.py"))
        found = _check_ids(findings)
        for expected in (
            "empty-test", "fake-pass", "hardcoded-sleep", "retry-loop",
            "swallowed-assert", "skipped-test", "expected-fail",
            "no-assert", "mock-only",
        ):
            self.assertIn(expected, found, f"missing {expected}: {findings}")

    def test_clean_fixture_is_clean(self):
        findings = scan_text("py_clean.py", _read("py_clean.py"))
        self.assertEqual(findings, [])

    def test_real_test_not_flagged_as_mock_only(self):
        findings = scan_text("t.py", "def test_real():\n    assert add(2, 3) == 5\n")
        self.assertEqual(_check_ids(findings), set())

    def test_unittest_constant_assertions_are_fake_pass(self):
        # Regression: unittest-style constant assertions are calls, not
        # `assert` statements, and used to escape the fake-pass check.
        for src in (
            "def test_x():\n    self.assertTrue(True)\n",
            "def test_x():\n    self.assertFalse(False)\n",
            "def test_x():\n    self.assertEqual(1, 1)\n",
        ):
            self.assertIn("fake-pass", _check_ids(scan_text("t.py", src)), src)
        # A real value assertion stays clean.
        self.assertNotIn(
            "fake-pass",
            _check_ids(scan_text(
                "t.py", "def test_x():\n    self.assertEqual(add(2, 3), 5)\n")))

    def test_swallowed_assert_ignores_unrelated_except_type(self):
        # Regression: except ValueError cannot swallow AssertionError,
        # so it must not be flagged — only handlers that can catch
        # AssertionError (bare, AssertionError, Exception, or a tuple
        # containing one) count as swallowing.
        for handler, flagged in (
            ("ValueError", False),
            ("(ValueError, TypeError)", False),
            ("AssertionError", True),
            ("", True),
            ("Exception", True),
            ("(ValueError, AssertionError)", True),
        ):
            code = (f"def test_x():\n"
                    "    try:\n"
                    "        assert f() == 1\n"
                    f"    except {handler}:\n"
                    "        pass\n")
            found = _check_ids(scan_text("t.py", code))
            if flagged:
                self.assertIn("swallowed-assert", found, handler)
            else:
                self.assertNotIn("swallowed-assert", found, handler)

    def test_unparseable_file_reports_parse_error(self):
        findings = scan_text("bad.py", "def test_broken(:\n")
        self.assertEqual(_check_ids(findings), {"parse-error"})


class JsChecksTests(unittest.TestCase):
    def test_cheating_fixture_flags_every_pattern(self):
        findings = scan_text("js_cheating.test.js", _read("js_cheating.test.js"))
        found = _check_ids(findings)
        for expected in (
            "skipped-test", "focused-test", "hardcoded-sleep",
            "fake-pass", "empty-test", "retry-loop", "swallowed-assert",
        ):
            self.assertIn(expected, found, f"missing {expected}: {findings}")

    def test_clean_fixture_is_clean(self):
        findings = scan_text("js_clean.test.js", _read("js_clean.test.js"))
        self.assertEqual(findings, [])


class DiffChecksTests(unittest.TestCase):
    DIFF = """diff --git a/tests/test_billing.py b/tests/test_billing.py
--- a/tests/test_billing.py
+++ b/tests/test_billing.py
@@ -10,7 +10,7 @@ def test_refund():
     total = compute_total(cart)
-    assert total == 59
+    assert True
@@ -30,4 +30,3 @@ def test_expired():
-    assert expired() is True
     return None
@@ -40,6 +40,7 @@ def test_flaky():
+    time.sleep(5)
     assert check() == 1
@@ -50,3 +50,2 @@ def test_old():
-def test_old():
-    assert 1 == 1
+    pass
"""

    def test_diff_flags_weakening(self):
        findings = analyze_diff(self.DIFF)
        found = _check_ids(findings)
        for expected in ("added-fake-pass", "removed-assert",
                         "added-sleep", "deleted-test"):
            self.assertIn(expected, found, f"missing {expected}: {findings}")

    def test_clean_diff_is_clean(self):
        diff = ("diff --git a/tests/test_a.py b/tests/test_a.py\n"
                "--- a/tests/test_a.py\n+++ b/tests/test_a.py\n"
                "@@ -1,2 +1,2 @@ def test_a():\n"
                "     x = 1\n-    assert x == 1\n+    assert x == 2\n")
        self.assertEqual(analyze_diff(diff), [])

    def test_deleted_async_test_is_flagged(self):
        diff = ("diff --git a/tests/test_async.py b/tests/test_async.py\n"
                "--- a/tests/test_async.py\n+++ b/tests/test_async.py\n"
                "@@ -1,3 +1,2 @@ async def test_flaky():\n"
                "-async def test_flaky():\n"
                "-    assert check() == 1\n"
                "+    pass\n")
        self.assertIn("deleted-test",
                      {f.check_id for f in analyze_diff(diff)})


class CliTests(unittest.TestCase):
    def _run(self, *args):
        root = os.path.join(os.path.dirname(__file__), "..")
        proc = subprocess.run(
            [sys.executable, "-m", "testguard", *args],
            cwd=root, capture_output=True, text=True, check=False,
        )
        return proc

    def test_cli_flags_cheating_fixtures(self):
        proc = self._run(os.path.join("tests", "fixtures", "py_cheating.py"))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("fake-pass", proc.stdout)

    def test_cli_clean_fixture_exits_zero(self):
        proc = self._run(os.path.join("tests", "fixtures", "py_clean.py"))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_cli_json_output_parses(self):
        proc = self._run("--format", "json",
                         os.path.join("tests", "fixtures", "py_cheating.py"))
        self.assertEqual(proc.returncode, 1)
        data = json.loads(proc.stdout)
        self.assertTrue(any(item["check"] == "fake-pass" for item in data))

    def test_cli_fail_on_none_never_fails(self):
        proc = self._run("--fail-on", "none",
                         os.path.join("tests", "fixtures", "py_cheating.py"))
        self.assertEqual(proc.returncode, 0)

    def test_cli_missing_path_exits_two(self):
        proc = self._run("no-such-dir-xyz")
        self.assertEqual(proc.returncode, 2)

    def test_scan_path_skips_non_test_files(self):
        findings = scan_path(os.path.join(FIXTURES, "py_clean.py"))
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
