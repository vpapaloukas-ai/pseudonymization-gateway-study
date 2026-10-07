import json
from types import SimpleNamespace

from helpers import FakeDetector, make_customer

from pgw import score
from pgw.audit import KINDS, GoldItem, build_gold
from pgw.briefs import Brief, Plant
from pgw.pipeline import exit_record, inbound, outbound
from pgw.vault import Vault

ADA = make_customer()
CRM = {ADA.email: ADA}
DET = FakeDetector(["John"])
ME = Plant("self_name", "Ada Okafor", ("Ada Okafor",), True, True, False)
JOHN = Plant("third_party", "John", ("John",), False, False, False)
CARD = Plant("card", "4111 1111 1111 1111", ("4111 1111 1111 1111",), False, False, True)
TOWN_LEAK = Plant("third_party", "Gemma", ("Gemma",), False, False, False)


def brief(plants, sender=ADA.email, matched=True, amount=4500, action="refund_item"):
    return Brief(email_id="dev-000", pid=ADA.pid, sender=sender, matched=matched,
                 case={"category": "refund", "order_no": "BW-482913", "order_items": [], "items": ["Ceramic table lamp"],
                       "wants": "", "double_charge": False, "repeat_contact": False},
                 gold={"category": "refund", "urgency": "normal", "action": action, "amount": amount,
                       "order_no": "BW-482913"},
                 self_name_form="full", plants=tuple(plants), style={}, hints={})


def reply_rec(data, stop="end_turn"):
    return {"stop_reason": stop, "text": json.dumps(data) if isinstance(data, dict) else data, "model": "m"}


GOOD = {"category": "refund", "urgency": "normal", "order": "[ORDER_1]", "action": "refund_item",
        "reply": "Dear [CUSTOMER_1], we will refund [AMOUNT_1] for [ORDER_1]."}


def run_one(text, plants, reply=GOOD, sender=ADA.email, matched=True):
    b = brief(plants, sender=sender, matched=matched)
    gold = build_gold(b, text, [], ADA)
    out = outbound(b.email_id, sender, text, CRM, DET)
    inb = inbound(b.email_id, 0, reply_rec(reply), out.vault) if out.message and not out.held else None
    return score.score_email(b, gold, ADA, out, inb, text), out, inb


def test_the_exit_record_carries_the_initials():
    assert exit_record(ADA).initials == ("A", "O")


def test_unrecognised_sender_is_held_and_nothing_is_sent():
    row, out, _ = run_one("Subject: x\n\nAda Okafor here", [ME], sender="ada@work.co.uk", matched=False)
    assert out.held == ("unrecognised_sender",) and out.message is None
    assert row["sent"] is False and row["holds"] == ["unrecognised_sender"]


def test_a_handled_email_is_scored_end_to_end():
    row, out, inb = run_one("Subject: Refund\n\nThe lamp from BW-482913 broke. John says hi. Ada Okafor", [ME, JOHN])
    assert "Ada Okafor" not in out.message and "BW-482913" not in out.message and "John" not in out.message
    assert inb.restored == "Dear Ada Okafor, we will refund £45.00 for BW-482913."
    assert row["handled"] and row["reply_correct"] and all(row["triage"].values())
    assert row["known"]["listed"] == [0, 2] and row["unknown"] == [{"kind": "third_party", "outcome": "masked", "stage": "exit"}]


def test_a_card_is_held_before_sending():
    row, out, _ = run_one("Subject: x\n\nAda Okafor, card 4111 1111 1111 1111", [ME, CARD])
    assert "card" in out.held and row["sent"] is False
    assert row["high_risk"] == [{"kind": "card", "outcome": "held", "stage": "exit"}]


def test_draft_held_after_sending_counts_as_sent_for_leakage():
    bad = dict(GOOD, reply="Dear [CUSTOMER_7].")
    row, _, inb = run_one("Subject: x\n\nAda Okafor and Gemma", [ME, TOWN_LEAK], reply=bad)
    assert "invented_token" in inb.draft and row["sent"] is True and row["handled"] is False
    assert row["unknown"] == [{"kind": "third_party", "outcome": "reached", "stage": "exit"}]


def test_a_first_name_greeting_is_a_correct_reply():
    first = dict(GOOD, reply="Hi [FIRST_NAME_1], we will refund [AMOUNT_1] for [ORDER_1].")
    row, _, inb = run_one("Subject: Refund\n\nThe lamp from BW-482913 broke. Ada Okafor", [ME], reply=first)
    assert row["handled"] and row["reply_correct"]
    assert inb.restored.startswith("Hi Ada,")


def test_wrong_amount_is_not_a_correct_reply():
    wrong = dict(GOOD, reply="Dear [CUSTOMER_1], we will refund [AMOUNT_2] for [ORDER_1].")
    row, _, _ = run_one("Subject: x\n\nAda Okafor, BW-482913", [ME], reply=wrong)
    assert row["handled"] and not row["reply_correct"]


def test_refusal_and_invalid_json_are_failures():
    out = outbound("e", ADA.email, "Subject: x\n\nAda Okafor", CRM, DET)
    assert inbound("e", 0, reply_rec("", stop="refusal"), out.vault).failure == "stop:refusal"
    assert inbound("e", 0, reply_rec("not json"), out.vault).failure == "invalid_json"


def test_a_known_value_left_in_the_message_is_a_leak():
    out = SimpleNamespace(email_id="e", held=(), message="Customer: [CUSTOMER_1]\n<<<\nOkafor here\n>>>",
                          vault=Vault().to_json(), known_hits=[], detections=[])
    b = brief([ME])
    gold = build_gold(b, "Subject: x\n\nAda Okafor, Okafor here", [], ADA)
    row = score.score_email(b, gold, ADA, out, None, "Subject: x\n\nAda Okafor, Okafor here")
    assert row["known"]["listed"][0] == 1


def test_a_skipped_gold_item_is_not_scored_but_is_counted():
    out = SimpleNamespace(email_id="e", held=(), message="<<<\nhello\n>>>", vault=Vault().to_json(),
                          known_hits=[], detections=[])
    skipped = GoldItem("skipped:third_party", "Gemma", ("Gemma",), "skipped", False, False, False)
    row = score.score_email(brief([ME]), [skipped], ADA, out, None, "")
    assert row["unknown"] == [] and row["high_risk"] == [] and row["skipped"] == 1
    assert score.summarise([row], [], {}, [])["audit.skipped"] == 1


def test_summary_has_every_key_with_zeros_and_two_denominators():
    s = score.summarise([], [], {"briefs": 0, "accepted": 0, "attempts": 0, "rejected_attempts": 0, "dropped": 0}, [])
    assert s["audit.skipped"] == 0
    keys = ["value.handled", "value.reply.over_handled", "value.reply.over_all", "holds.false", "holds.false_clean"]
    for lst in ("listed", "unlisted"):
        keys += [f"leaks.known.{lst}.{k}" for k in ("mentions", "mentions_sent", "emails", "emails_sent")]
        keys.append(f"contrast.known.{lst}.mentions")
    for key in keys:
        assert s[key] == [0, 0], key
    assert "contrast.known.mentions" not in s
    assert s["holds.false_by_reason"] == {g: 0 for g in score.HOLD_GROUPS_ALL if g != "no_answer"}
    for k in ("third_party", "new_phone", "new_address", "unplanned", "card", "iban"):
        for pre in ("unknown", "high_risk"):
            if f"{pre}.{k}" in s:
                assert s[f"{pre}.{k}"]["n_at_exit"] == 0 and s[f"{pre}.{k}"]["held_at_exit"] == 0
    for field in ("category", "urgency", "order", "action"):
        assert s[f"value.triage.{field}.over_handled"] == [0, 0]
    for g in score.HOLD_GROUPS_ALL:
        assert s[f"holds.{g}"] == [0, 0]
    for k in ("third_party", "new_phone", "new_address", "unplanned"):
        assert s[f"unknown.{k}"] == {"masked": 0, "held": 0, "reached": 0, "n": 0, "n_at_exit": 0, "held_at_exit": 0}
    for k in ("card", "iban", "unplanned"):
        assert s[f"high_risk.{k}"] == {"masked": 0, "held": 0, "reached": 0, "n": 0, "n_at_exit": 0, "held_at_exit": 0}
    for k in KINDS:
        for pre in ("unknown", "high_risk"):
            assert s[f"{pre}.unplanned.{k}"] == {"masked": 0, "held": 0, "reached": 0, "n": 0, "n_at_exit": 0,
                                                 "held_at_exit": 0}, f"{pre}.unplanned.{k}"


def test_a_leak_in_another_form_is_counted():
    out = SimpleNamespace(email_id="e", held=(), message="<<<\n[CUSTOMER_1] Okafor\n>>>",
                          vault=Vault().to_json(), known_hits=[], detections=[])
    gold = build_gold(brief([ME]), "Subject: x\n\nAda Okafor here", [], ADA)
    row = score.score_email(brief([ME]), gold, ADA, out, None, "")
    assert row["known"]["listed"] == [1, 1]


def test_headline_and_contrast_share_one_denominator():
    r1, _, _ = run_one("Subject: x\n\nAda Okafor here", [ME])
    r2, _, _ = run_one("Subject: x\n\nAda Okafor here", [ME], sender="ada@work.co.uk", matched=False)
    assert r1["sent"] and not r2["sent"]
    s = score.summarise([r1, r2], [], {}, [])
    total = r1["known"]["listed"][1] + r2["known"]["listed"][1]
    assert total == 2
    assert s["leaks.known.listed.mentions"][1] == s["contrast.known.listed.mentions"][1] == total
    assert s["leaks.known.listed.mentions_sent"][1] == r1["known"]["listed"][1]


IBAN = Plant("iban", "GB29 NWBK 6016 1331 9268 19", ("GB29 NWBK 6016 1331 9268 19",), False, False, True)


def test_high_risk_held_at_the_sender_is_not_credited_to_the_exit_check():
    row, _, _ = run_one("Subject: x\n\nAda Okafor, iban GB29 NWBK 6016 1331 9268 19", [ME, IBAN],
                        sender="ada@work.co.uk", matched=False)
    assert row["high_risk"] == [{"kind": "iban", "outcome": "held", "stage": "sender"}]
    s = score.summarise([row], [], {}, [])
    assert s["high_risk.iban"]["held"] == 1 and s["high_risk.iban"]["n_at_exit"] == 0
    assert s["high_risk.iban"]["held_at_exit"] == 0


def test_false_holds_use_the_nothing_planted_set():
    row, out, _ = run_one("Subject: x\n\nHello, tracking number 7845 2210 9934", [])
    assert "digit_run" in out.held
    assert row["nothing_planted"] is True and row["clean"] is False
    s = score.summarise([row], [], {}, [])
    assert s["holds.false"] == [1, 1] and s["holds.false_clean"] == [0, 0]
    assert s["holds.false_by_reason"]["leftover_pattern"] == 1 or sum(s["holds.false_by_reason"].values()) == 1
    assert row["unknown"] == [{"kind": "unplanned:card", "outcome": "held", "stage": "exit"}]
    assert s["unknown.unplanned.card"]["n"] == 1 and s["unknown.unplanned"]["n"] == 1
    assert all(s[f"unknown.unplanned.{k}"]["n"] == 0 for k in KINDS if k != "card")


def test_an_unplanned_high_risk_item_has_its_own_line():
    row, _, _ = run_one("Subject: x\n\nAda Okafor, card 4111 1111 1111 1111", [ME])
    assert row["high_risk"] == [{"kind": "unplanned:card", "outcome": "held", "stage": "exit"}]
    s = score.summarise([row], [], {}, [])
    assert s["high_risk.unplanned.card"]["n"] == 1 and s["high_risk.unplanned"]["n"] == 1
    assert s["high_risk.unplanned.card"]["held_at_exit"] == 1 and s["high_risk.card"]["n"] == 0


def test_an_unmapped_exit_reason_raises():
    import pytest
    out = SimpleNamespace(email_id="e", held=("mystery",), message=None, vault=None, known_hits=[], detections=[])
    with pytest.raises(ValueError):
        score.score_email(brief([ME]), [], ADA, out, None, "")


def test_control_passes():
    score.control()


def test_abbreviation_initials_are_not_given_to_the_exit_check():
    assert exit_record(make_customer("Umar", "Kavanagh")).initials == ()
    assert exit_record(make_customer()).initials == ("A", "O")


def _row(action, handled, action_ok):
    return {"email_id": "x", "gold_action": action, "handled": handled, "sent": handled, "holds": [],
            "nothing_planted": True, "clean": True, "reply_correct": handled,
            "triage": {"category": True, "urgency": True, "order": True, "action": action_ok},
            "known": {"listed": [0, 0], "unlisted": [0, 0]}, "unknown": [], "high_risk": [], "skipped": 0,
            "contrast": {"known": {"listed": [0, 0], "unlisted": [0, 0]}, "high_risk": [0, 0]}}


def test_per_action_counts_are_always_written_and_add_up_to_the_headline():
    from pgw.policy import ACTIONS
    empty = score.summarise([], [], {}, [])
    for a in ACTIONS:
        assert empty[f"value.by_action.{a}"] == {"n": 0, "handled": 0, "action_correct": 0}
    rows = [_row("refund_item", True, True), _row("refund_item", True, False), _row("refund_item", False, False),
            _row("escalate", True, True), _row("cancel", False, False), _row("refund_item", False, True)]
    s = score.summarise(rows, [], {}, [])
    assert s["value.by_action.refund_item"] == {"n": 4, "handled": 2, "action_correct": 1}   # the unhandled row with action True is not counted
    assert s["value.by_action.escalate"] == {"n": 1, "handled": 1, "action_correct": 1}
    assert s["value.by_action.cancel"] == {"n": 1, "handled": 0, "action_correct": 0}
    assert s["value.by_action.resend"] == {"n": 0, "handled": 0, "action_correct": 0}
    assert {k for k in s if k.startswith("value.by_action.")} == {f"value.by_action.{a}" for a in ACTIONS}
    assert sum(s[f"value.by_action.{a}"]["n"] for a in ACTIONS) == s["n_emails"]
    assert sum(s[f"value.by_action.{a}"]["handled"] for a in ACTIONS) == s["value.handled"][0]
    assert sum(s[f"value.by_action.{a}"]["action_correct"] for a in ACTIONS) == s["value.triage.action.over_handled"][0]
