from datetime import date

import pytest

from pgw import policy
from pgw.crm import Item, Order
from pgw.policy import Case, decide

LAMP, THROW = Item("Ceramic table lamp", 4500), Item("Wool throw", 6500)
TODAY = date(2026, 10, 5)


def order(status, delivered=None, dispatched=None, items=(LAMP, THROW)):
    return Order("BW-000001", date(2026, 8, 1), status, dispatched, delivered, items)


DELIVERED_RECENT = order("delivered", delivered=date(2026, 9, 5), dispatched=date(2026, 9, 2))   # 30 days
DELIVERED_OLD = order("delivered", delivered=date(2026, 9, 4), dispatched=date(2026, 9, 1))      # 31 days
DISPATCHED_LATE = order("dispatched", dispatched=date(2026, 9, 27))                              # 8 days
DISPATCHED_RECENT = order("dispatched", dispatched=date(2026, 9, 28))                            # 7 days
PROCESSING = order("processing")


@pytest.mark.parametrize("case, expected", [
    (Case("refund", DELIVERED_RECENT, (LAMP,)), ("refund_item", "normal", 4500)),
    (Case("refund", DELIVERED_RECENT, (THROW, LAMP)), ("full_refund", "normal", 11000)),
    (Case("refund", DELIVERED_OLD, (LAMP,)), ("explain", "normal", None)),
    (Case("refund", DISPATCHED_LATE, (LAMP,)), ("explain", "normal", None)),
    (Case("late_delivery", DISPATCHED_LATE), ("resend", "normal", None)),
    (Case("late_delivery", DISPATCHED_RECENT), ("explain", "normal", None)),
    (Case("damaged_or_wrong", DELIVERED_RECENT, (LAMP,), wants="replacement"), ("resend", "high", None)),
    (Case("damaged_or_wrong", DELIVERED_RECENT, (LAMP, THROW), wants="refund"), ("refund_item", "high", 11000)),
    (Case("change_of_address", PROCESSING), ("update_address", "low", None)),
    (Case("change_of_address", DISPATCHED_LATE), ("explain", "normal", None)),
    (Case("cancellation", PROCESSING), ("cancel", "normal", None)),
    (Case("cancellation", DELIVERED_RECENT), ("explain", "normal", None)),
    (Case("billing_question", PROCESSING), ("explain", "low", None)),
    (Case("billing_question", PROCESSING, double_charge=True), ("escalate", "high", None)),
    (Case("account_access", None), ("escalate", "high", None)),
    (Case("complaint", None), ("escalate", "normal", None)),
    (Case("complaint", PROCESSING, repeat_contact=True), ("escalate", "high", None)),
    (Case("cancellation", PROCESSING, repeat_contact=True), ("cancel", "high", None)),
])
def test_decide(case, expected):
    d = decide(case, TODAY)
    assert (d.action, d.urgency, d.amount) == expected


def test_policy_text_names_every_category_action_and_threshold():
    for word in policy.CATEGORIES + policy.ACTIONS + policy.URGENCIES:
        assert word in policy.POLICY_TEXT
    assert f"{policy.RETURN_DAYS} days" in policy.POLICY_TEXT and f"{policy.LATE_DAYS} days" in policy.POLICY_TEXT
