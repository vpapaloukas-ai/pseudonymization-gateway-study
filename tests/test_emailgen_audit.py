import json
import re
from types import SimpleNamespace

import anthropic
import pytest
from helpers import make_customer

from pgw import emailgen
from pgw.audit import build_gold, pattern_scan
from pgw.briefs import Brief, Plant
from pgw.model_call import ServiceStop

ADA = make_customer()


def brief(plants, **kw):
    base = dict(email_id="dev-000", pid=ADA.pid, sender=ADA.email, matched=True,
                case={"category": "refund", "order_no": "BW-482913", "order_items": ["Ceramic table lamp", "Wool throw"],
                      "items": ["Ceramic table lamp"], "wants": "", "double_charge": False, "repeat_contact": False,
                      "reason": "changed their mind"},
                gold={"category": "refund", "urgency": "normal", "action": "refund_item", "amount": 4500,
                      "order_no": "BW-482913"},
                self_name_form="full", plants=tuple(plants),
                style={"tone": "polite", "register": "formal", "typos": False, "quoted_thread": False, "signature": True},
                hints={})
    base.update(kw)
    return Brief(**base)


ME = Plant("self_name", "Ada Okafor", ("Ada Okafor",), True, True, False)
JOHN = Plant("third_party", "John", ("John",), False, False, False)


def reply(body, stop="end_turn"):
    text = json.dumps({"subject": "Refund", "body": body})
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason=stop, model="claude-opus-5-5",
                           usage=SimpleNamespace(input_tokens=1, output_tokens=1), _request_id="r", to_dict=lambda: {})


class Scripted:
    def __init__(self, replies):
        self.replies, self.messages = list(replies), self

    def create(self, **kwargs):
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class Boom(anthropic.APIError):
    def __init__(self):
        Exception.__init__(self, "boom")


def test_generator_message_lists_every_plant_and_the_hint():
    b = brief([ME, JOHN], hints={"third_party_relation": "my husband"})
    msg = emailgen.generator_message(b, ADA)
    assert "- Ada Okafor" in msg and "- John" in msg and "my husband" in msg and "Ceramic table lamp" in msg


def test_first_contact_and_repeat_contact_are_said_explicitly():
    first = emailgen.generator_message(brief([ME]), ADA)
    assert "first contact about this issue" in first and "not their first contact" not in first
    again = emailgen.generator_message(brief([ME], case={**brief([ME]).case, "repeat_contact": True}), ADA)
    assert "not their first contact" in again and "do not mention any earlier" not in again
    assert "already contacted" not in emailgen.describe(brief([ME], case={**brief([ME]).case, "repeat_contact": True}))


def test_refunds_carry_the_no_damage_line_and_damaged_or_wrong_carries_neither_line():
    refund = emailgen.generator_message(brief([ME]), ADA)
    assert "Their reason for the refund: changed their mind" in refund and "they need not say so" in refund
    assert "Do not describe any item as damaged" in refund
    damage = emailgen.generator_message(brief([ME], case={**brief([ME]).case, "category": "damaged_or_wrong",
                                                          "wants": "refund", "reason": ""}), ADA)
    assert "Do not describe any item as damaged" not in damage and "Their reason" not in damage


def test_the_item_is_fine_line_is_only_for_a_delivered_order():
    from datetime import date
    from pgw.crm import Item, Order
    delivered = emailgen.generator_message(brief([ME]), ADA)
    assert "The item is fine and is what they ordered; they need not say so." in delivered
    assert "They have not received it yet." not in delivered
    assert delivered.count("need not say") == 1
    transit = make_customer(orders=(Order("BW-482913", date(2026, 10, 1), "dispatched", date(2026, 10, 2), None,
                                          (Item("Ceramic table lamp", 4500), Item("Wool throw", 6500))),))
    msg = emailgen.generator_message(brief([ME]), transit)
    assert "Their reason for the refund: changed their mind. They have not received it yet." in msg
    assert "The item is fine" not in msg and msg.count("need not say") == 0
    assert "Do not describe any item as damaged, broken, faulty or wrong." in msg.splitlines()


def test_the_import_guard_for_english_day_and_month_names_exists():
    # Cannot catch a non-English LC_TIME here (monkeypatching the locale is not portable); it only checks that the
    # guard is in the source as a plain `if` raising RuntimeError, and that its condition holds under this locale.
    import inspect
    src = inspect.getsource(emailgen)
    assert 'if f"{REFERENCE_DATE:%A %B}" != "Monday October":' in src and "raise RuntimeError(" in src
    assert f"{emailgen.REFERENCE_DATE:%A %B}" == "Monday October"


def test_the_quoted_thread_sentence_is_pinned():
    line = "it promises nothing (no refund, replacement, amount or date)"
    quoted = emailgen.generator_message(brief([ME], style={**brief([ME]).style, "quoted_thread": True}), ADA)
    assert line in quoted
    assert line not in emailgen.generator_message(brief([ME]), ADA)


def test_complaints_say_whether_an_order_is_meant():
    base = brief([ME]).case
    with_order = emailgen.describe(brief([ME], case={**base, "category": "complaint"}))
    assert "how their order with Ceramic table lamp" in with_order
    none = emailgen.describe(brief([ME], case={**base, "category": "complaint", "order_no": None, "items": [],
                                               "order_items": []}))
    assert "not with any particular order" in none and "do not mention an order" in none
    assert "do not mention an order" in emailgen.ISSUE["account_access"]


def _days_back(n):
    from datetime import timedelta
    from pgw.crm import REFERENCE_DATE
    return REFERENCE_DATE - timedelta(days=n)


@pytest.mark.parametrize("n,phrase", [
    (0, "today"), (1, "yesterday"), (2, "last Saturday"), (6, "last Tuesday"),
    (7, "about a week ago"), (10, "about a week ago"), (11, "about two weeks ago"), (17, "about two weeks ago"),
    (18, "about three weeks ago"), (24, "about three weeks ago"), (25, "about a month ago"),
    (38, "about a month ago"), (39, "about six weeks ago"), (52, "about six weeks ago"),
    (53, "about two months ago"), (75, "about two months ago"), (76, "a few months ago"), (120, "a few months ago")])
def test_ago_bands_at_every_edge(n, phrase):
    assert emailgen._ago(_days_back(n)) == phrase


def test_ago_names_the_weekday_with_on_this_week_and_last_before_it(monkeypatch):
    from datetime import date
    monkeypatch.setattr(emailgen, "REFERENCE_DATE", date(2026, 10, 8))          # a Thursday; this Monday is 5 October
    assert date(2026, 10, 8).strftime("%A") == "Thursday"
    assert emailgen._ago(date(2026, 10, 6)) == "on Tuesday"
    assert emailgen._ago(date(2026, 10, 5)) == "on Monday"
    assert emailgen._ago(date(2026, 10, 4)) == "last Sunday"
    assert emailgen._ago(date(2026, 10, 2)) == "last Friday"
    assert emailgen._ago(date(2026, 10, 7)) == "yesterday"


@pytest.mark.parametrize("n,phrase", [
    (0, "the same day"), (1, "the next day"), (2, "a couple of days later"), (3, "a few days later"),
    (4, "a few days later"), (5, "about a week later"), (9, "about a week later"), (10, "about two weeks later"),
    (17, "about two weeks later"), (18, "several weeks later"), (40, "several weeks later")])
def test_gap_bands_at_every_edge(n, phrase):
    from datetime import date, timedelta
    assert emailgen._gap(date(2026, 8, 1), date(2026, 8, 1) + timedelta(days=n)) == phrase


def test_ago_never_asserts_the_wrong_side_of_a_policy_line():
    from pgw import policy
    for n in range(0, 121):
        p = emailgen._ago(_days_back(n))
        if p in ("about six weeks ago", "about two months ago", "a few months ago"):
            assert n > policy.RETURN_DAYS, (n, p)
        if p in ("today", "yesterday", "about a week ago", "about two weeks ago", "about three weeks ago") or p.startswith(("on ", "last ")):
            assert n <= policy.RETURN_DAYS, (n, p)
        if p in ("about two weeks ago", "about three weeks ago"):
            assert n > policy.LATE_DAYS, (n, p)
        if p in ("today", "yesterday") or p.startswith(("on ", "last ")):
            assert n <= policy.LATE_DAYS, (n, p)
    assert emailgen._ago.__doc__ and "month" in emailgen._ago.__doc__


def test_the_order_status_line_carries_the_weekday_rounded_phrases_and_status():
    msg = emailgen.generator_message(brief([ME]), ADA)
    assert ("Today is Monday 5 October 2026. Background the customer knows (they may refer to these facts in these "
            "words or their own, or leave out when things happened; they must not list dates, give a count of days, "
            "be more precise than these phrases, or state today's date): the order was placed about a month ago; "
            "it was dispatched the next day and delivered a few days later (about a month ago); "
            "it is now delivered. Any time phrase in the email must agree with these. Do not contradict these facts.") in msg.splitlines()
    proc = emailgen.generator_message(brief([ME], case={**brief([ME]).case, "order_no": "BW-500001"}), ADA)
    assert "the order was placed yesterday; it is now processing. Any time phrase" in proc
    none = emailgen.generator_message(brief([ME], case={**brief([ME]).case, "order_no": None}), ADA)
    assert "the order was placed" not in none and "Today is" not in none


def test_the_latest_event_always_carries_its_own_time_phrase():
    from pgw.briefs import build_briefs
    from pgw.crm import DEV_PIDS, build_crm
    crm = {c.pid: c for c in build_crm()}
    checked = [(ADA, brief([ME]))] + [(crm[b.pid], b) for b in build_briefs(list(crm.values()), seed=1, n=100,
                                                                            pids=DEV_PIDS, prefix="dev")]
    seen = 0
    for c, b in checked:
        if not b.case["order_no"]:
            continue
        o = next(o for o in c.orders if o.order_no == b.case["order_no"])
        line = _status_line(emailgen.generator_message(b, c))
        latest = o.delivered or o.dispatched
        if latest:
            assert f" ({emailgen._ago(latest)}); it is now {o.status}. Any time phrase" in line, b.email_id
        else:
            assert f"placed {emailgen._ago(o.placed)}; it is now processing. Any time phrase" in line, b.email_id
        seen += 1
    assert seen > 50


def test_a_phrase_in_parentheses_appears_only_when_it_differs_from_the_previous_event():
    from dataclasses import replace
    from datetime import timedelta
    from pgw.crm import REFERENCE_DATE
    o = ADA.orders[0]
    late = replace(o, placed=REFERENCE_DATE - timedelta(days=9), dispatched=REFERENCE_DATE - timedelta(days=8),
                   delivered=REFERENCE_DATE - timedelta(days=4))
    c = replace(ADA, orders=(late, ADA.orders[1]))
    line = _status_line(emailgen.generator_message(brief([ME]), c))
    assert ("the order was placed about a week ago; it was dispatched the next day and delivered a few days later "
            "(last Thursday); it is now delivered. ") in line
    assert "dispatched the next day (" not in line
    tail = replace(o, placed=REFERENCE_DATE - timedelta(days=20), dispatched=REFERENCE_DATE - timedelta(days=9),
                   delivered=REFERENCE_DATE - timedelta(days=8))
    line = _status_line(emailgen.generator_message(brief([ME]), replace(ADA, orders=(tail, ADA.orders[1]))))
    assert ("the order was placed about three weeks ago; it was dispatched about two weeks later (about a week ago) "
            "and delivered the next day (about a week ago); it is now delivered. ") in line
    transit = replace(o, placed=REFERENCE_DATE - timedelta(days=12), dispatched=REFERENCE_DATE - timedelta(days=3),
                      delivered=None, status="dispatched")
    line = _status_line(emailgen.generator_message(brief([ME]), replace(ADA, orders=(transit, ADA.orders[1]))))
    assert ("the order was placed about two weeks ago; it was dispatched about a week later (last Friday); "
            "it is now dispatched. ") in line


def _status_line(msg):
    return next(ln for ln in msg.splitlines() if ln.startswith("Today is "))


TODAY = "Today is Monday 5 October 2026. "


def test_no_order_date_appears_anywhere_in_the_message():
    import calendar
    from pgw.briefs import build_briefs
    from pgw.crm import DEV_PIDS, build_crm
    line = _status_line(emailgen.generator_message(brief([ME]), ADA))
    assert line.startswith("Today is Monday 5 October 2026") and "about a month ago" in line
    crm = {c.pid: c for c in build_crm()}
    checked = [(ADA, brief([ME]))] + [(crm[b.pid], b) for b in build_briefs(list(crm.values()), seed=1, n=100,
                                                                            pids=DEV_PIDS, prefix="dev")]
    seen = 0
    for c, b in checked:
        if not b.case["order_no"]:
            continue
        seen += 1
        o = next(o for o in c.orders if o.order_no == b.case["order_no"])
        msg = emailgen.generator_message(b, c)
        line = _status_line(msg)
        assert line.startswith(TODAY) and msg.count(TODAY) == 1, b.email_id
        rest = line[len(TODAY):]
        assert not re.search(r"\d", rest), b.email_id                      # no digit at all after the today line
        assert "days ago" not in msg, b.email_id
        assert not any(m in rest for m in calendar.month_name[1:]), b.email_id
        whole = msg.replace(TODAY, "", 1)                                   # order dates: the whole message
        for d in (o.placed, o.dispatched, o.delivered):
            if d:
                assert emailgen._when(d) not in whole and d.isoformat() not in whole, b.email_id
    assert seen > 50


def test_the_no_damage_line_is_on_refunds_and_complaints_with_orders():
    base = brief([ME]).case

    # Refund: the plain line is present and count("need not say") == 1
    refund = emailgen.generator_message(brief([ME]), ADA)
    assert "Do not describe any item as damaged, broken, faulty or wrong." in refund.splitlines()
    assert "The item is fine and is what they ordered; they need not say so." in refund
    assert refund.count("need not say") == 1

    # Complaint with an order: the new line appears exactly once
    complaint_with_order = emailgen.generator_message(brief([ME], case={**base, "category": "complaint"}), ADA)
    assert complaint_with_order.count("Do not describe any item as damaged, broken, faulty or wrong; they need not say the items are fine.") == 1
    assert "Do not describe any item as damaged" in complaint_with_order

    # Complaint without an order: no no-damage line
    complaint_no_order = emailgen.generator_message(brief([ME], case={**base, "category": "complaint", "order_no": None, "items": [], "order_items": []}), ADA)
    assert "Do not describe any item as damaged" not in complaint_no_order
    assert "need not say" not in complaint_no_order

    # Every other category from ISSUE except refund, complaint and damaged_or_wrong: neither string
    for cat in emailgen.ISSUE:
        if cat in ("refund", "damaged_or_wrong", "complaint", "complaint_no_order"):
            continue
        case = {**base, "category": cat}
        msg = emailgen.generator_message(brief([ME], case=case), ADA)
        assert "Do not describe any item as damaged" not in msg and "need not say" not in msg, cat

    # damaged_or_wrong: neither string
    damaged = emailgen.generator_message(brief([ME], case={**base, "category": "damaged_or_wrong", "wants": "refund",
                                                           "reason": ""}), ADA)
    assert "Do not describe any item as damaged" not in damaged and "need not say" not in damaged


def test_every_plant_gets_its_role_line_and_the_fake_writer_still_extracts_only_values():
    plants = [ME, JOHN, Plant("order_no", "BW-482913", ("BW-482913",), True, True, False),
              Plant("account", "BWC1234567", ("BWC1234567",), True, True, False),
              Plant("phone_on_file", "07700 900123", ("07700 900123",), True, True, False),
              Plant("amount_on_file", "£45.00", ("£45.00",), True, True, False),
              Plant("new_phone", "07700 900555", ("07700 900555",), False, False, False),
              Plant("new_address", "5 Mill Lane, Ludlow SY8 1AA", ("5 Mill Lane", "SY8 1AA"), False, False, False),
              Plant("card", "4111 1111 1111 1111", ("4111 1111 1111 1111",), False, False, True),
              Plant("iban", "GB00 SYNT 1234", ("GB00 SYNT 1234",), False, False, True)]
    b = brief(plants, hints={"third_party_relation": "my wife"})
    msg = emailgen.generator_message(b, ADA)
    tail = msg.split("What each of these is (")[1]
    for role in ("BW-482913 is their order number", "BWC1234567 is their account number (not an order number)",
                 "07700 900123 is their own phone number", "£45.00 is the price they paid for Ceramic table lamp",
                 "John is my wife (a member of their household or circle, not a member of staff)",
                 "07700 900555 is a new phone number of theirs",
                 "is their new home address (they have moved; it is not the delivery address of this order)",
                 "which they include although they should not", "is their bank account for a refund"):
        assert role in tail
    assert "is the new delivery address for this order" not in tail
    assert "Ada Okafor is" not in tail and "\n- " not in tail
    change = brief(plants, hints={"third_party_relation": "my wife"}, case={**b.case, "category": "change_of_address"})
    assert "5 Mill Lane, Ludlow SY8 1AA is the new delivery address for this order" in emailgen.generator_message(change, ADA)
    user = msg
    fake = emailgen.FakeWriter().create(messages=[{"content": user}])
    body = json.loads(fake.content[0].text)["body"]
    assert emailgen.check_exact(b, "x", body) == []
    assert body.splitlines()[1:-1] == [p.value for p in plants]


IBAN = Plant("iban", "GB00 SYNT 1234", ("GB00 SYNT 1234",), False, False, True)
NEW_ADDRESS = Plant("new_address", "5 Mill Lane, Ludlow SY8 1AA", ("5 Mill Lane", "SY8 1AA"), False, False, False)


def test_the_iban_role_line_depends_on_the_category():
    base = brief([ME]).case
    complaint = emailgen.generator_message(brief([ME, IBAN], case={**base, "category": "complaint"}), ADA)
    assert "which they include although they should not" in complaint.split("What each of these is (")[1]
    assert "for a refund" not in complaint.split("What each of these is (")[1]
    for cat in ("refund", "damaged_or_wrong"):
        msg = emailgen.generator_message(brief([ME, IBAN], case={**base, "category": cat}), ADA)
        assert "GB00 SYNT 1234 is their bank account for a refund" in msg


def test_new_address_without_an_order_is_just_a_new_home_address():
    base = brief([ME]).case
    msg = emailgen.generator_message(brief([ME, NEW_ADDRESS], case={**base, "category": "complaint", "order_no": None,
                                                                    "items": [], "order_items": []}), ADA)
    tail = msg.split("What each of these is (")[1]
    assert "is their new home address (they have moved)" in tail and "this order" not in tail
    with_order = emailgen.generator_message(brief([ME, NEW_ADDRESS], case={**base, "category": "complaint"}), ADA)
    assert "it is not the delivery address of this order" in with_order


def test_an_initials_self_name_makes_no_double_full_stop():
    initials = Plant("self_name", "A. O.", ("A. O.",), True, True, False)
    msg = emailgen.generator_message(brief([initials], self_name_form="initials"), ADA)
    assert "A. O.." not in msg and "refer to themselves as: A. O." in msg


def test_check_exact():
    b = brief([ME, JOHN])
    assert emailgen.check_exact(b, "Hi", "Ada Okafor and John") == []
    assert emailgen.check_exact(b, "Hi", "Ada and john") == ["Ada Okafor", "John"]


def test_regenerates_until_exact_and_records_every_attempt(tmp_path):
    out = tmp_path / "generation.jsonl"
    emailgen.generate(Scripted([reply("Ada Okafor only"), reply("Ada Okafor and John")]), [brief([ME, JOHN])],
                      {ADA.pid: ADA}, out)
    rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert [(r["attempt"], r["ok"]) for r in rows] == [(0, False), (1, True)]
    assert emailgen.accepted(out)["dev-000"]["body"] == "Ada Okafor and John"
    assert emailgen.stats(out) == {"briefs": 1, "accepted": 1, "attempts": 2, "rejected_attempts": 1, "dropped": 0}


def test_resume_after_a_service_stop_does_not_repeat_attempts(tmp_path):
    out = tmp_path / "generation.jsonl"
    with pytest.raises(ServiceStop):
        emailgen.generate(Scripted([reply("nope"), Boom()]), [brief([ME, JOHN])], {ADA.pid: ADA}, out)
    emailgen.generate(Scripted([reply("Ada Okafor and John")]), [brief([ME, JOHN])], {ADA.pid: ADA}, out)
    rows = [json.loads(x) for x in out.read_text(encoding="utf-8").splitlines()]
    assert [r["attempt"] for r in rows] == [0, 1]


def test_dropped_after_max_attempts(tmp_path):
    out = tmp_path / "generation.jsonl"
    emailgen.generate(Scripted([reply("x")] * emailgen.MAX_ATTEMPTS), [brief([ME, JOHN])], {ADA.pid: ADA}, out)
    assert emailgen.accepted(out) == {} and emailgen.stats(out)["dropped"] == 1


def test_fake_writer_satisfies_the_exact_check(tmp_path):
    out = tmp_path / "generation.jsonl"
    emailgen.generate(emailgen.FakeWriter(), [brief([ME, JOHN])], {ADA.pid: ADA}, out)
    assert "dev-000" in emailgen.accepted(out)


def test_pattern_scan_finds_contact_details():
    found = pattern_scan("mail x.y@inboxly.co.uk or 07700 900999, paid £4.99")
    assert ("email", "x.y@inboxly.co.uk") in found and ("phone", "07700 900999") in found and ("amount", "£4.99") in found


def test_gold_adds_unplanned_finds_and_skips_plants_record_values_company_and_products():
    b = brief([ME, JOHN])
    text = "Subject: Refund\n\nAda Okafor here, with John. Courier Sarah left the Ceramic table lamp. Brightwell Home, call 07700 900999."
    items = [{"kind": "name", "text": "Ada Okafor"}, {"kind": "name", "text": "John"},
             {"kind": "name", "text": "Sarah"}, {"kind": "other", "text": "Brightwell Home"},
             {"kind": "other", "text": "Ceramic table lamp"}]
    gold = build_gold(b, text, items, ADA)
    unplanned = sorted((g.kind, g.value) for g in gold if g.origin == "audit")
    assert unplanned == [("unplanned:name", "Sarah"), ("unplanned:phone", "07700 900999")]
    assert any(g.origin == "record_scan" and g.value == "Ada Okafor" for g in gold)
    assert any(g.origin == "planted" and g.value == "John" and not g.known for g in gold)


def test_gold_refuses_when_a_planted_known_value_is_not_found():
    with pytest.raises(AssertionError):
        build_gold(brief([ME]), "Subject: x\n\nno name here", [], ADA)


def test_a_first_name_plant_inside_the_full_name_is_found():
    first = Plant("self_name", "Ada", ("Ada",), True, True, False)
    gold = build_gold(brief([first]), "Subject: x\n\nThanks,\nAda Okafor", [], ADA)
    assert any(g.origin == "record_scan" and g.value == "Ada Okafor" for g in gold)


def test_skip_rule_keeps_real_unplanned_values():
    b = brief([ME, JOHN])
    text = ("Subject: x\n\nAda Okafor here. Ada wrote. Johnson called; also write ada.okafor2@postbox-mail.co.uk; "
            "paid £120.50.")
    items = [{"kind": "name", "text": "Johnson"}, {"kind": "name", "text": "Okafor"},
             {"kind": "email", "text": "ada.okafor2@postbox-mail.co.uk"}, {"kind": "amount", "text": "£120.50"}]
    gold = build_gold(b, text, items, ADA)
    audit_values = {g.value for g in gold if g.origin == "audit"}
    assert {"Johnson", "ada.okafor2@postbox-mail.co.uk", "£120.50"} <= audit_values
    okafor = [g for g in gold if g.value == "Okafor"]
    assert okafor and all(g.kind == "skipped:name" and g.origin == "skipped" for g in okafor)


def test_check_exact_needs_word_boundaries():
    assert emailgen.check_exact(brief([ME, JOHN]), "Hi", "Ada Okafor and Johnson") == ["John"]


@pytest.mark.parametrize("possessive", ["Okafor's", "Okafor’s"])
def test_a_possessive_of_a_scanned_name_is_skipped(possessive):
    text = f"Subject: x\n\nMs Okafor here. {possessive} order is late."
    ms = Plant("self_name", "Ms Okafor", ("Ms Okafor",), True, True, False)
    gold = build_gold(brief([ms], self_name_form="title_last"), text, [{"kind": "name", "text": possessive}], ADA)
    item = [g for g in gold if g.value == possessive]
    assert item and all(g.kind == "skipped:name" and g.origin == "skipped" for g in item)


def test_unplanned_card_and_bank_are_high_risk_only_if_valid():
    text = "Subject: x\n\nAda Okafor here. tracking number 7845 2210 9934, and 4111 1111 1111 1111."
    gold = {g.value: g for g in build_gold(brief([ME]), text, [], ADA) if g.origin == "audit"}
    assert gold["7845 2210 9934"].kind == "unplanned:card" and gold["7845 2210 9934"].high_risk is False
    assert gold["4111 1111 1111 1111"].kind == "unplanned:card" and gold["4111 1111 1111 1111"].high_risk is True


def test_the_role_heading_marks_the_roles_as_background():
    msg = emailgen.generator_message(brief([ME, JOHN]), ADA)
    assert "do not restate these descriptions" in msg
    assert "Must include, exactly:\n- Ada Okafor\n- John\n" in msg


def test_fake_writer_and_check_exact_pass_for_all_dev_briefs():
    from pgw.briefs import build_briefs
    from pgw.crm import DEV_PIDS, build_crm
    crm = {c.pid: c for c in build_crm()}
    for b in build_briefs(list(crm.values()), seed=1, n=100, pids=DEV_PIDS, prefix="dev"):
        fake = emailgen.FakeWriter().create(messages=[{"content": emailgen.generator_message(b, crm.get(b.pid) or ADA)}])
        assert emailgen.check_exact(b, "x", json.loads(fake.content[0].text)["body"]) == [], b.email_id
