import json
from datetime import timedelta

from helpers import make_customer

from pgw import exitcheck, pipeline, policy, prompts
from pgw.crm import REFERENCE_DATE, build_crm, money
from pgw.known import mask_known
from pgw.model_call import EchoClient, ask
from pgw.vault import Vault

ADA = make_customer()


def test_system_prompt_carries_policy_date_and_rules():
    s = prompts.SYSTEM_PROMPT
    assert policy.POLICY_TEXT in s and "2026-10-05" in s
    for phrase in ("{SUM: [AMOUNT_a], [AMOUNT_b]}", "{DIFF: [AMOUNT_a], [AMOUNT_b]}", "first minus the second",
                   "must state the amount refunded", "by its order placeholder", "first-name placeholder"):
        assert phrase in s, phrase
    assert ("- order: the order placeholder from the customer record that the email is about, or an empty string "
            "if it is about no order.") in s
    assert "{{" not in s and "}}" not in s and "[ORDER_n]" not in s


def test_the_system_prompt_says_the_day_counts_are_calculated_and_to_use_them():
    s = prompts.SYSTEM_PROMPT
    assert ("Today is 2026-10-05. Beside each date, the customer record gives how many days ago it was: these counts "
            "are calculated for you, so use them, not your own date arithmetic, for the policy's day limits.") in s
    assert "2026-10-05" in s


def test_days_counts_back_from_the_reference_date():
    assert prompts._days(REFERENCE_DATE) == "today"
    assert prompts._days(REFERENCE_DATE - timedelta(days=1)) == "1 day ago"
    assert prompts._days(REFERENCE_DATE - timedelta(days=2)) == "2 days ago"
    assert prompts._days(REFERENCE_DATE - timedelta(days=42)) == "42 days ago"
    d = REFERENCE_DATE - timedelta(days=36)
    assert prompts._dated(d) == f"{d.isoformat()} (36 days ago)"


def test_the_summary_gives_elapsed_days_beside_each_date():
    v = Vault()
    mask_known("", ADA, v)
    s = prompts.record_summary(ADA, v)
    o = ADA.orders[0]
    days = lambda d: (REFERENCE_DATE - d).days
    assert (f"placed {o.placed.isoformat()} ({days(o.placed)} days ago), "
            f"dispatched {o.dispatched.isoformat()} ({days(o.dispatched)} days ago), "
            f"delivered {o.delivered.isoformat()} (30 days ago)") in s
    assert days(o.delivered) == 30
    assert f"status processing, placed {ADA.orders[1].placed.isoformat()} (1 day ago). Items:" in s


def test_the_new_digits_beside_the_dates_never_trip_the_exit_check_for_any_customer():
    crm = build_crm()
    assert len(crm) == 200
    for c in crm:
        v = Vault()
        mask_known("", c, v)
        message = prompts.user_message("", prompts.record_summary(c, v))
        assert exitcheck.check(message, pipeline.exit_record(c)) == [], c.pid


def test_schema_enums_are_the_policy_lists():
    props = prompts.TRIAGE_SCHEMA["schema"]["properties"]
    assert props["category"]["enum"] == list(policy.CATEGORIES)
    assert props["action"]["enum"] == list(policy.ACTIONS)
    assert props["urgency"]["enum"] == list(policy.URGENCIES)
    assert prompts.TRIAGE_SCHEMA["schema"]["additionalProperties"] is False


def test_record_summary_uses_only_seeded_tokens_and_no_clear_values():
    v = Vault()
    mask_known("", ADA, v)
    before = v.tokens()
    s = prompts.record_summary(ADA, v)
    assert v.tokens() == before
    for clear in (ADA.full, ADA.phone, ADA.email, "BW-482913", money(4500), ADA.street):
        assert clear not in s
    assert "Ceramic table lamp" in s and "2026-09-05" in s and "[ORDER_1]" in s
    assert "(first name: [FIRST_NAME_1])" in s
    assert "(the sum of the item prices; no delivery charges or taxes)" in s


def test_user_message_shape():
    assert prompts.user_message("Hi", "Customer: [CUSTOMER_1]") == (
        "Customer record:\nCustomer: [CUSTOMER_1]\n\nEmail:\n<<<\nHi\n>>>")


def test_echo_client_answers_in_the_schema():
    rec = ask(EchoClient(), "m", "s", "Customer: [CUSTOMER_1]\nOrder [ORDER_1]", "high",
              output_format=prompts.TRIAGE_SCHEMA)
    data = json.loads(rec["text"])
    assert set(data) == {"category", "urgency", "order", "action", "reply"} and data["order"] == "[ORDER_1]"


def test_the_reply_format_payment_and_authorship_rules_are_in_the_prompt():
    s = prompts.SYSTEM_PROMPT
    for line in ("- Write the reply with line breaks: the greeting, each paragraph and the sign-off on separate lines.",
                 "- The customer record holds no payment information: never claim what has already been charged or paid.",
                 "- Do not say who or what wrote the reply."):
        assert line in s
    assert s.index("Greet the customer") < s.index("Write the reply with line breaks") < s.index("When the action is full_refund")
