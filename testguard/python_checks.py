"""AST-based checks for Python test files.

Every check works on the parsed syntax tree, not on text matching, so
``assert True`` hidden behind formatting or a comment still gets caught,
and a legitimate ``time.sleep`` in a *helper* (not in a test) is ignored.
"""

from __future__ import annotations

import ast

from .findings import Finding


def _decorator_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    names: list[str] = []
    for dec in node.decorator_list:
        try:
            names.append(ast.unparse(dec))
        except Exception:
            names.append("")
    return names


def _is_mock_name(name: str, mock_names: set[str]) -> bool:
    return name in mock_names


def _collect_mock_names(tree: ast.AST) -> set[str]:
    """Variable names bound to Mock / MagicMock / patch objects."""
    mocks: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value = node.value
            if isinstance(value, ast.Call):
                func = value.func
                fname = ""
                if isinstance(func, ast.Name):
                    fname = func.id
                elif isinstance(func, ast.Attribute):
                    fname = func.attr
                if fname in ("Mock", "MagicMock", "patch", "mocker"):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            mocks.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if isinstance(node.value, ast.Call):
                func = node.value.func
                fname = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
                if fname in ("Mock", "MagicMock", "patch"):
                    mocks.add(node.target.id)
    return mocks


def _is_unittest_assert(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr.startswith("assert"):
        return True
    return False


def _is_pytest_raises(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.With):
            for item in sub.items:
                expr = item.context_expr
                if isinstance(expr, ast.Call):
                    func = expr.func
                    name = ""
                    if isinstance(func, ast.Attribute):
                        name = f"{ast.unparse(func.value)}.{func.attr}"
                    elif isinstance(func, ast.Name):
                        name = func.id
                    if name.endswith("pytest.raises") or name == "raises":
                        return True
    return False


def _contains_assert(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assert):
            return True
        if isinstance(sub, ast.Call) and _is_unittest_assert(sub):
            return True
    return False


def _is_empty_body(body: list[ast.stmt]) -> bool:
    stmts = [s for s in body if not (
        isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
        and isinstance(s.value.value, str)
    )]
    return len(stmts) == 0 or (len(stmts) == 1 and isinstance(stmts[0], ast.Pass))


def _is_constant_truthy(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and bool(node.value) is True


def _handler_swallows(handler: ast.ExceptHandler) -> bool:
    """True when the except block does nothing but pass / continue."""
    body = [s for s in handler.body if not isinstance(s, ast.Expr)]
    if not body:
        return True
    return all(isinstance(s, (ast.Pass, ast.Continue)) for s in body)


def _handler_catches_assertion(handler: ast.ExceptHandler) -> bool:
    """True when this handler can catch AssertionError.

    An `except ValueError: pass` handler cannot swallow an assertion
    failure, so flagging it as swallowed-assert was a false high:
    AssertionError propagates past it and the test fails as it should.
    Unknown exception names are treated as not catching it — the safe
    direction for a high-severity gate.
    """
    return _exc_catches_assertion(handler.type)


def _exc_catches_assertion(exc: ast.AST | None) -> bool:
    """True when an except-clause expression can catch AssertionError."""
    if exc is None:
        return True  # bare except: catches everything
    if isinstance(exc, ast.Tuple):
        return any(_exc_catches_assertion(e) for e in exc.elts)
    name = ""
    if isinstance(exc, ast.Name):
        name = exc.id
    elif isinstance(exc, ast.Attribute):
        name = exc.attr
    return name in ("AssertionError", "Exception", "BaseException")


def _check_test_function(
    path: str, func: ast.FunctionDef | ast.AsyncFunctionDef
) -> list[Finding]:
    findings: list[Finding] = []
    lineno = func.lineno

    # --- skipped / xfail decorators -------------------------------------
    for dec in _decorator_names(func):
        low = dec.lower()
        if "skip" in low:
            findings.append(Finding(path, lineno, "skipped-test", "low",
                                    "Test is skipped and never runs.",
                                    dec))
        elif "xfail" in low and "strict=true" not in low.replace(" ", ""):
            findings.append(Finding(path, lineno, "expected-fail", "low",
                                    "xfail without strict=True: failure is "
                                    "expected and never blocks CI.", dec))
        elif "retry" in low or "tenacity" in low:
            findings.append(Finding(path, lineno, "retry-loop", "high",
                                    "Test is wrapped in a retry decorator — "
                                    "flakiness is hidden instead of fixed.",
                                    dec))

    # --- empty test ------------------------------------------------------
    if _is_empty_body(func.body):
        findings.append(Finding(path, lineno, "empty-test", "high",
                                "Test body is empty (only pass/docstring) — "
                                "it can never fail.", func.name))
        return findings  # nothing else worth checking in an empty test

    # --- pytest.skip() inside the body -----------------------------------
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            func_name = ast.unparse(node.func) if hasattr(ast, "unparse") else ""
            if func_name in ("pytest.skip", "pytest.xfail"):
                findings.append(Finding(path, node.lineno, "skipped-test", "low",
                                        f"Test bails out via {func_name}().",
                                        func_name))
                break

    # --- assertions ------------------------------------------------------
    asserts = [n for n in ast.walk(func) if isinstance(n, ast.Assert)]
    unittest_asserts = [n for n in ast.walk(func)
                        if isinstance(n, ast.Call) and _is_unittest_assert(n)]
    has_assert = bool(asserts or unittest_asserts) or _is_pytest_raises(func)

    if not has_assert:
        findings.append(Finding(path, lineno, "no-assert", "medium",
                                "Test runs code but asserts nothing — "
                                "it passes no matter what the code does.",
                                func.name))
    else:
        for a in asserts:
            if _is_constant_truthy(a.test):
                findings.append(Finding(path, a.lineno, "fake-pass", "high",
                                        "Assertion is a constant truthy value "
                                        "and can never fail.",
                                        ast.unparse(a)[:120]))
        # unittest-style assertions escape the check above: they are
        # calls, not `assert` statements, so assertTrue(True) and
        # assertEqual(1, 1) used to pass clean. Same rule, same check id.
        for call in unittest_asserts:
            attr = call.func.attr if isinstance(call.func, ast.Attribute) else ""
            args = call.args
            fake = False
            if attr == "assertTrue" and args and _is_constant_truthy(args[0]):
                fake = True
            elif attr == "assertFalse" and args and isinstance(args[0], ast.Constant) \
                    and args[0].value is False:
                fake = True
            elif attr in ("assertEqual", "assertIs") and len(args) >= 2 \
                    and isinstance(args[0], ast.Constant) \
                    and isinstance(args[1], ast.Constant) \
                    and type(args[0].value) is type(args[1].value) \
                    and args[0].value == args[1].value:
                fake = True
            if fake:
                findings.append(Finding(path, call.lineno, "fake-pass", "high",
                                        "Assertion compares constants / a "
                                        "constant truthy value and can never "
                                        "fail.",
                                        ast.unparse(call)[:120]))

    # --- hardcoded sleep --------------------------------------------------
    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Attribute):
                name = f"{ast.unparse(node.func.value)}.{node.func.attr}"
            elif isinstance(node.func, ast.Name):
                name = node.func.id
            if name in ("time.sleep", "asyncio.sleep", "sleep"):
                findings.append(Finding(path, node.lineno, "hardcoded-sleep",
                                        "medium",
                                        "Hardcoded sleep in a test hides "
                                        "timing flakiness and slows the suite.",
                                        ast.unparse(node)[:120]))

    # --- retry loop around assertions -------------------------------------
    for node in ast.walk(func):
        if isinstance(node, (ast.For, ast.While, ast.AsyncFor)):
            if not _contains_assert(node):
                continue
            has_try = any(isinstance(n, ast.Try) for n in ast.walk(node))
            is_range_loop = isinstance(node, ast.For) and isinstance(node.iter, ast.Call) \
                and getattr(node.iter.func, "id", "") == "range"
            if has_try or is_range_loop:
                findings.append(Finding(path, node.lineno, "retry-loop", "high",
                                        "Assertion inside a retry loop: the "
                                        "test passes if it succeeds once.",
                                        ast.unparse(node).splitlines()[0][:120]))
                break

    # --- swallowed assertions ---------------------------------------------
    for node in ast.walk(func):
        if isinstance(node, ast.Try):
            if _contains_assert(node) and any(
                _handler_swallows(h) and _handler_catches_assertion(h)
                for h in node.handlers
            ):
                findings.append(Finding(path, node.lineno, "swallowed-assert",
                                        "high",
                                        "Assertion inside try/except that "
                                        "swallows the failure (pass/continue).",
                                        "try/except: pass"))
                break

    # --- mock-only test ----------------------------------------------------
    if has_assert:
        mock_names = _collect_mock_names(func)
        mock_asserts = 0
        value_asserts = 0
        for a in asserts:
            names = {n.id for n in ast.walk(a.test) if isinstance(n, ast.Name)}
            if names and names <= (mock_names | {"self", "True", "False", "None"}):
                mock_asserts += 1
            else:
                value_asserts += 1
        for call in unittest_asserts:
            names = {n.id for n in ast.walk(call) if isinstance(n, ast.Name)}
            if names and names <= (mock_names | {"self", "True", "False", "None"}):
                mock_asserts += 1
            else:
                value_asserts += 1
        # mock.assert_called* style assertions with no value assertions
        mock_method_asserts = [
            n for n in ast.walk(func)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr.startswith("assert_called")
        ]
        if mock_names and value_asserts == 0 and (mock_asserts or mock_method_asserts):
            findings.append(Finding(path, lineno, "mock-only", "medium",
                                    "Test only asserts on mocks — it verifies "
                                    "the test doubles, not the real code.",
                                    func.name))
    return findings


def check_python(path: str, text: str) -> list[Finding]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return [Finding(path, exc.lineno or 1, "parse-error", "low",
                        f"Test file does not parse: {exc.msg}",
                        (exc.text or "").strip()[:120])]
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test") or any(
                "pytest" in d or "parametrize" in d
                for d in _decorator_names(node)
            ):
                findings.extend(_check_test_function(path, node))
    return findings
