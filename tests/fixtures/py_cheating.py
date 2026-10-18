"""Fixture: a test file full of manipulation patterns.

Each function demonstrates one way a green suite can lie.
Do NOT copy these patterns into real tests.
"""

import time

import pytest
from unittest.mock import MagicMock


def add(a, b):
    return a + b


def test_empty():
    pass


def test_fake_pass():
    assert True


def test_sleepy():
    time.sleep(2)
    assert add(1, 2) == 3


def test_retry():
    for _ in range(3):
        try:
            assert add(1, 2) == 3
            break
        except AssertionError:
            continue


def test_swallowed():
    try:
        assert add(1, 2) == 3
    except AssertionError:
        pass


@pytest.mark.skip(reason="flaky on CI")
def test_skipped():
    assert add(1, 2) == 3


@pytest.mark.xfail
def test_expected_fail():
    assert add(1, 2) == 4


def test_no_assert():
    add(1, 2)


def test_mock_only():
    client = MagicMock()
    client.get("/health")
    client.get.assert_called_once_with("/health")


def test_real():
    assert add(2, 3) == 5
