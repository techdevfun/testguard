"""Fixture: a clean Python test file — testguard must report nothing."""

import pytest


def add(a, b):
    return a + b


def test_add_returns_sum():
    assert add(2, 3) == 5


def test_add_rejects_text():
    with pytest.raises(TypeError):
        add("a", 1)


def test_add_is_commutative():
    assert add(2, 3) == add(3, 2)
