import pytest
from helpers import make_customer

from pgw.known_scan import counts, occurrences

ADA = make_customer()
DAN = make_customer("Daniel", "Hale")


def fields(text, c=ADA):
    return [(o.field, o.form, o.listed) for o in occurrences(text, c)]


def test_full_name_counts_once():
    assert fields("Ada Okafor here") == [("name", "full", True)]


def test_unlisted_forms_are_found():
    assert ("name", "nickname", False) in fields("Cheers, Dan", DAN)
    assert ("town", "town", False) in fields("I live in Whitby")


def test_broader_separators_than_the_gateway():
    assert ("phone", "national", True) in fields("ring 07700/900/123")


def test_order_and_amount_forms():
    got = fields("Order BW-482913 for £45, and 482913 again")
    assert got.count(("order", "order", True)) == 1 and ("order", "digits", True) in got
    assert ("amount", "amount", True) in got


def test_counts_key_on_normalised_text():
    c = counts("ada okafor and Ada Okafor", ADA)
    assert sum(c.values()) == 2 and len(c) == 1


@pytest.mark.parametrize("text", ["A.O.", "A. O."])
def test_initials_dotted_uppercase(text):
    assert ("name", "initials", True) in fields(f"Regards, {text}")


@pytest.mark.parametrize("text", ["AO", "A O", "a.o.", "ao", "a o"])
def test_undotted_or_lowercase_is_not_initials(text):
    assert not [f for f in fields(f"Regards, {text}") if f[1] == "initials"]


def test_spaced_digits_are_not_an_order_number():
    assert ("order", "digits", True) not in fields("ref 48 29 13 and 48-29-13")
    assert ("order", "digits", True) in fields("ref 482913")


def test_amount_is_not_found_inside_a_longer_figure():
    assert ("amount", "amount", True) not in fields("paid £120.50 and £45.99")
    assert fields("paid £120 and £45.00").count(("amount", "amount", True)) == 2


def test_initials_never_span_a_sentence_break():
    for first, last, text in [("Kieran", "Ingram", "I live in the U.K. I love it"),
                              ("Alistair", "Iqbal", "Option A. I think so.")]:
        assert not [f for f in fields(text, make_customer(first, last)) if f[1] == "initials"]


def test_abbreviation_initials_get_no_form():
    assert not [f for f in fields("shipping to the U.K. today", make_customer("Umar", "Kavanagh")) if f[1] == "initials"]
