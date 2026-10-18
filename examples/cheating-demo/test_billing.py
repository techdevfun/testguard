"""Example: what a cheating test file looks like in the wild.

Run:  python -m testguard examples/cheating-demo
Expect: exit 1, with fake-pass / retry-loop / swallowed-assert /
hardcoded-sleep / skipped-test findings.
"""

import time

import pytest


def charge_card(amount_cents):
    return {"status": "charged", "amount": amount_cents}


def flaky_gateway(amount_cents):
    return charge_card(amount_cents)


@pytest.mark.skip(reason="fails on CI sometimes")
def test_charge_is_recorded():
    assert charge_card(5000)["status"] == "charged"


def test_gateway_eventually_charges():
    for _ in range(5):
        try:
            assert flaky_gateway(5000)["status"] == "charged"
            break
        except AssertionError:
            time.sleep(1)
            continue


def test_refund_never_fails():
    try:
        assert charge_card(0)["status"] == "charged"
    except AssertionError:
        pass
