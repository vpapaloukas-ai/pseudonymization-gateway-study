import dataclasses

from pgw import names, policy
from pgw.briefs import MIX, UNMATCHED, build_briefs, case_of
from pgw.crm import DEV_PIDS, TEST_PIDS, build_crm

CRM = build_crm()
BY_PID = {c.pid: c for c in CRM}
DEV = build_briefs(CRM, seed=1, n=100, pids=DEV_PIDS, prefix="dev")


def kinds(b):
    return {p.kind for p in b.plants}


def test_deterministic():
    again = build_briefs(CRM, seed=1, n=100, pids=DEV_PIDS, prefix="dev")
    assert [dataclasses.asdict(b) for b in again] == [dataclasses.asdict(b) for b in DEV]


def test_senders_come_from_their_half():
    assert all(int(b.pid[1:]) in DEV_PIDS for b in DEV)
    test = build_briefs(CRM, seed=2, n=50, pids=TEST_PIDS, prefix="test")
    assert all(int(b.pid[1:]) in TEST_PIDS for b in test)
    assert [b.email_id for b in test[:2]] == ["test-000", "test-001"]


def test_mix_floors():
    n = len(DEV)
    assert sum(not b.matched for b in DEV) == round(UNMATCHED * n)
    assert sum(bool(kinds(b) & {"card", "iban"}) for b in DEV) >= round(MIX["high_risk"] * n)
    assert sum("third_party" in kinds(b) for b in DEV) >= round(MIX["third_party"] * n)
    assert sum(b.self_name_form == "nickname" for b in DEV) >= round(MIX["nickname"] * n)


def test_unmatched_senders_are_not_in_the_crm():
    emails = {c.email for c in CRM}
    for b in DEV:
        assert (b.sender in emails) == b.matched
        if b.matched:
            assert b.sender == BY_PID[b.pid].email


def test_self_name_is_first_and_listed_unless_a_nickname():
    for b in DEV:
        p = b.plants[0]
        assert p.kind == "self_name" and p.known
        assert p.listed == (b.self_name_form != "nickname")
        if b.self_name_form == "nickname":
            assert p.value == names.NICKNAMES[BY_PID[b.pid].first]


def test_unknown_plants_differ_from_the_record():
    # The dev seed happens to draw no colliding town or postcode; test-sized batches on the test half do.
    test_like = [b for s in (2, 3, 4) for b in build_briefs(CRM, seed=s, n=300, pids=TEST_PIDS, prefix="test")]
    for b in DEV + test_like:
        c = BY_PID[b.pid]
        for p in b.plants:
            if p.kind == "third_party":
                assert p.value in names.THIRD_PARTY_NAMES and not p.known
            if p.kind == "new_phone":
                assert p.value != c.phone and p.value not in {x.phone for x in CRM}
            if p.kind == "new_address":
                assert p.parts[0] != c.street and len(p.parts) == 2
                assert p.parts[1] != c.postcode
                street, rest = p.value.rsplit(", ", 1)
                town = rest.rsplit(" ", 2)[0]       # "<town> <outward> <inward>": towns are one word, postcodes have one space
                assert street == p.parts[0] and rest.endswith(" " + p.parts[1])
                assert town in names.TOWNS and town != c.town
            if p.kind == "card":
                assert p.value in names.TEST_CARDS and p.high_risk
            if p.kind == "iban":
                assert p.value.replace(" ", "") != c.iban and "SYNT" in p.value.replace(" ", "") and p.high_risk


def test_gold_is_the_policy_applied_to_the_case():
    for b in DEV:
        d = policy.decide(case_of(b, BY_PID[b.pid]))
        assert b.gold["action"] == d.action and b.gold["urgency"] == d.urgency and b.gold["amount"] == d.amount
        assert b.gold["category"] == b.case["category"] and b.gold["order_no"] == b.case["order_no"]


def test_address_changes_always_carry_a_new_address():
    for b in DEV:
        if b.case["category"] == "change_of_address":
            assert "new_address" in kinds(b)


def test_damage_needs_a_delivered_order():
    for b in DEV:
        if b.case["category"] == "damaged_or_wrong":
            o = next(o for o in BY_PID[b.pid].orders if o.order_no == b.case["order_no"])
            assert o.status == "delivered"


def _all_runs():
    return [DEV] + [build_briefs(CRM, seed=s, n=300, pids=TEST_PIDS, prefix="test") for s in (2, 3, 4)]


def test_only_a_repeat_contact_quotes_an_earlier_reply():
    for briefs in _all_runs():
        for b in briefs:
            assert not b.style["quoted_thread"] or b.case["repeat_contact"], b.email_id


def test_every_refund_has_a_reason_without_damage_and_no_other_category_has_one():
    for briefs in _all_runs():
        for b in briefs:
            if b.case["category"] == "refund":
                assert b.case["reason"] in names.REFUND_REASONS, b.email_id
            else:
                assert b.case["reason"] == ""


def test_third_parties_match_their_relation_gender():
    for briefs in _all_runs():
        for b in briefs:
            for p in b.plants:
                if p.kind == "third_party":
                    gender = dict(names.RELATIONS)[b.hints["third_party_relation"]]
                    allowed = {"m": names.THIRD_PARTY_MALE, "f": names.THIRD_PARTY_FEMALE}.get(gender, names.THIRD_PARTY_NAMES)
                    assert p.value in allowed, b.email_id


def test_new_address_and_iban_plants_collide_with_no_crm_record():
    streets, postcodes = {c.street for c in CRM}, {c.postcode for c in CRM}
    ibans = {c.iban for c in CRM}
    for briefs in _all_runs():
        for b in briefs:
            for p in b.plants:
                if p.kind == "new_address":
                    assert p.parts[0] not in streets and p.parts[1] not in postcodes, b.email_id
                if p.kind == "iban":
                    assert p.value.replace(" ", "") not in ibans, b.email_id


def test_no_initials_plant_for_abbreviation_initials():
    runs = [DEV] + [build_briefs(CRM, seed=s, n=300, pids=TEST_PIDS, prefix="test") for s in (2, 3, 4)]
    for briefs in runs:
        for b in briefs:
            c = BY_PID[b.pid]
            if c.first[0] + c.last[0] in names.DOTTED_ABBREVIATIONS:
                assert b.self_name_form != "initials", b.email_id


def test_cancellations_and_address_changes_never_target_a_late_order():
    from pgw.crm import REFERENCE_DATE
    checked = dispatched = 0
    for run in _all_runs():
        for b in run:
            if b.case["category"] in ("cancellation", "change_of_address"):
                o = next(o for o in BY_PID[b.pid].orders if o.order_no == b.case["order_no"])
                checked += 1
                if o.status != "processing":
                    assert (REFERENCE_DATE - o.dispatched).days <= policy.LATE_DAYS, b.email_id
                    dispatched += 1
    assert checked > 50
    assert dispatched >= 1          # the filter keeps recent dispatched orders, not only processing ones


def test_refunds_never_target_a_late_undelivered_order():
    from pgw.crm import REFERENCE_DATE
    refunds = dispatched = delivered = 0
    for run in _all_runs():
        for b in run:
            if b.case["category"] == "refund":
                o = next(o for o in BY_PID[b.pid].orders if o.order_no == b.case["order_no"])
                refunds += 1
                if o.status == "dispatched":
                    dispatched += 1
                    assert (REFERENCE_DATE - o.dispatched).days <= policy.LATE_DAYS, b.email_id
                elif o.status == "delivered":
                    delivered += 1
    assert refunds > 50 and delivered > 40     # a filter that also drops delivered targets fails here
    assert dispatched >= 1          # the filter keeps recent dispatched orders


def test_cancellations_and_address_changes_never_have_a_delivered_order():
    for run in _all_runs():
        for b in run:
            if b.case["category"] in ("cancellation", "change_of_address") and b.case["order_no"]:
                o = next(o for o in BY_PID[b.pid].orders if o.order_no == b.case["order_no"])
                assert o.status in ("processing", "dispatched")
