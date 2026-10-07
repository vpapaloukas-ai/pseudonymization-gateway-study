import re

from pgw import names
from pgw.crm import (CRM_SEED, DEV_PIDS, REFERENCE_DATE, TEST_PIDS, WORD_NAME_PIDS, build_crm, money,
                     unused_phones)


def _iban_ok(s):
    return int("".join(str(int(ch, 36)) for ch in s[4:] + s[:4])) % 97 == 1


def _luhn(digits):
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def test_build_is_deterministic():
    assert build_crm(CRM_SEED) == build_crm(CRM_SEED)


def test_two_hundred_customers_with_unique_names_and_emails():
    crm = build_crm()
    assert len(crm) == 200
    assert len({(c.first, c.last) for c in crm}) == 200
    assert len({c.email for c in crm}) == 200
    assert all(c.email.split("@")[1] in names.MAIL_DOMAINS for c in crm)


def test_identifiers_are_synthetic_by_construction():
    for c in build_crm():
        assert re.fullmatch(r"07700 900\d{3}", c.phone)
        assert c.iban[4:8] == "SYNT" and _iban_ok(c.iban)
        assert re.fullmatch(r"BWC\d{7}", c.account)
        assert all(re.fullmatch(r"BW-\d{6}", o.order_no) for o in c.orders)


def test_phones_and_order_numbers_are_unique():
    crm = build_crm()
    assert len({c.phone for c in crm}) == 200
    orders = [o.order_no for c in crm for o in c.orders]
    assert len(orders) == len(set(orders))


def test_order_dates_agree_with_status():
    for c in build_crm():
        assert 1 <= len(c.orders) <= 3
        for o in c.orders:
            assert o.placed < REFERENCE_DATE and 1 <= len(o.items) <= 3
            assert o.total == sum(i.price for i in o.items)
            if o.status == "processing":
                assert o.dispatched is None and o.delivered is None
            elif o.status == "dispatched":
                assert o.placed < o.dispatched <= REFERENCE_DATE and o.delivered is None
            else:
                assert o.status == "delivered" and o.dispatched < o.delivered <= REFERENCE_DATE


def test_word_named_customers_are_in_both_halves():
    words = sorted(int(c.pid[1:]) for c in build_crm() if c.first in names.WORD_FIRST_NAMES)
    assert words == sorted(WORD_NAME_PIDS)
    assert any(p in DEV_PIDS for p in words) and any(p in TEST_PIDS for p in words)


def test_money_format():
    assert (money(4500), money(123456), money(5)) == ("£45.00", "£1,234.56", "£0.05")


def test_unused_phones_avoid_the_crm():
    crm = build_crm()
    spare = unused_phones(crm)
    assert len(spare) == 800 and not set(spare) & {c.phone for c in crm}


def test_name_lists_are_disjoint_and_nicknames_belong_to_first_names():
    lists = [names.FIRST_NAMES, names.WORD_FIRST_NAMES, names.LAST_NAMES, names.THIRD_PARTY_NAMES,
             list(names.NICKNAMES.values())]
    flat = [x for lst in lists for x in lst]
    assert len(flat) == len(set(flat))
    assert set(names.NICKNAMES) <= set(names.FIRST_NAMES)


def test_test_cards_are_luhn_valid():
    assert all(_luhn(c.replace(" ", "")) for c in names.TEST_CARDS)


def _orders(pids=None):
    return [o for c in build_crm() if pids is None or int(c.pid[1:]) in pids for o in c.orders]


def test_no_dispatched_order_is_more_than_twenty_days_old():
    assert all((REFERENCE_DATE - o.dispatched).days <= 20 for o in _orders() if o.status == "dispatched")


def test_at_least_a_tenth_of_all_orders_are_processing():
    orders = _orders()
    assert sum(o.status == "processing" for o in orders) >= 0.10 * len(orders)


def test_the_dev_half_has_at_least_ten_processing_orders():
    assert sum(o.status == "processing" for o in _orders(set(DEV_PIDS))) >= 10
