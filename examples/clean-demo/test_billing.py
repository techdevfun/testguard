"""Example: the same billing tests written honestly.

Run:  python -m testguard examples/clean-demo
Expect: exit 0, "clean".
"""

import pytest


def charge_card(amount_cents):
    if amount_cents <= 0:
        raise ValueError("amount must be positive")
    return {"status": "charged", "amount": amount_cents}


def test_charge_is_recorded():
    result = charge_card(5000)
    assert result["status"] == "charged"
    assert result["amount"] == 5000


def test_charge_rejects_non_positive_amount():
    with pytest.raises(ValueError):
        charge_card(0)
