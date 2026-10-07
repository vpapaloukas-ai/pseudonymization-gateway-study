import ast
import dataclasses
from pathlib import Path

import pytest

from pgw.crm import iban_gb
from pgw.exitcheck import HOLD_GROUPS, Record, check, control

OTHER_IBAN = iban_gb("SYNT", "654321", "87654321")
SPACED_IBAN = " ".join(OTHER_IBAN[i:i + 4] for i in range(0, len(OTHER_IBAN), 4))
REC = Record(names=("Ada", "Okafor"), case_sensitive=(), sequences=("07700 900123", "BWC1234567", "1234567",
             "GB02SYNT12345612345678", "YO21 3XX", "BW-482913", "482913"),
             phrases=("ada.okafor@postbox-mail.co.uk", "ada.okafor", "12 Larkspur Road"), amounts=(4500, 11000))


def test_imports_nothing_from_the_package():
    tree = ast.parse((Path(__file__).resolve().parent.parent / "pgw" / "exitcheck.py").read_text(encoding="utf-8"))
    mods = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    mods += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not any(m == "pgw" or m.startswith("pgw.") for m in mods)


def test_a_clean_message_may_leave():
    msg = ("Customer record:\nCustomer: [CUSTOMER_1]\nOrder [ORDER_1]: status delivered, placed 2026-09-01, "
           "dispatched 2026-09-02. Items: Glass storage jars, set of 3 [AMOUNT_1]. Total [AMOUNT_1].\n\n"
           "Email:\n<<<\nHi, it arrived on 05/10/2026 but 3 jars were broken. 2 weeks ago I asked. Thanks, [CUSTOMER_1]\n>>>")
    assert check(msg, REC) == []


@pytest.mark.parametrize("text, reason", [
    ("Okafor here", "known_name"), ("ring 07700900123", "known_number"), ("ring +44 7700 900123", "known_number"),
    ("ref 482913", "known_number"), ("at 12 larkspur  road", "known_phrase"), ("it cost £45", "known_amount"),
    ("it cost 110.00", "known_amount"),
])
def test_known_values_hold(text, reason):
    assert reason in check(text, REC)


def test_name_parts_inside_words_do_not_hold():
    assert check("Adams and Okaforth", REC) == []


def test_case_sensitive_word_names():
    will = Record(names=("Will", "Hale"), case_sensitive=("Will",), sequences=(), phrases=(), amounts=())
    assert check("will you help?", will) == [] and "known_name" in check("Will here", will)


@pytest.mark.parametrize("text, reason", [
    ("card 4111 1111 1111 1111", "card"), ("card 4111-1111-1111-1111", "card"),
    (f"iban {SPACED_IBAN}", "iban"), (f"iban {OTHER_IBAN}", "iban"), ("NI QQ 12 34 56 C", "nino"),
    ("see [CREDIT_CARD_1]", "high_risk_token"), ("see [IBAN_CODE_1]", "high_risk_token"),
    ("mail me at someone@else.co.uk", "email"), ("ring 01632 960123", "phone"), ("code 1234 5678", "digit_run"),
    ("ring 01632.960.123", "phone"), ("ring 07700.900.123", "phone"),
    ("card 4111.1111.1111.1111", "card"), ("card 4111  1111  1111  1111", "card"),
    ("card 4111 1111 1111 1111", "card"), ("amex 3782 822463 10005", "card"),
    (f"iban {SPACED_IBAN.lower()}", "iban"), ("code 1234 5678", "digit_run"),
])
def test_patterns_hold(text, reason):
    assert reason in check(text, None)


def test_an_invalid_card_number_is_not_a_card():
    assert "card" not in check("4111 1111 1111 1112", None)


def test_unseeded_address_holds():
    assert "email" in check("I also use [CUSTOMER_1]-at-work: ada.okafor@harrowfield-logistics.co.uk", REC)


@pytest.mark.parametrize("text", ["placed 2026-09-14", "on 05/10/2026", "set of 3", "order 2 of 3",
                                  "at 14:30", "[ORDER_1] [AMOUNT_2]", "on 05.10.2026", "waited 10 days, 3 items"])
def test_dates_and_ordinary_numbers_do_not_hold(text):
    assert check(text, REC) == []


def test_bare_numbers_are_not_known_amounts():
    assert check("I have 45 items and waited 45 minutes", REC) == []


def test_every_reason_has_a_group():
    assert set(HOLD_GROUPS) == {"high_risk_token", "card", "iban", "nino", "email", "phone", "digit_run",
                                "known_name", "known_number", "known_phrase", "known_amount", "known_initials"}
    assert HOLD_GROUPS["known_initials"] == "known_value"


REC_I = dataclasses.replace(REC, initials=("A", "O"))


@pytest.mark.parametrize("text", ["Regards, A.O.", "Regards, A. O."])
def test_known_initials_hold(text):
    assert "known_initials" in check(text, REC_I)
    assert "known_initials" not in check(text, REC)


@pytest.mark.parametrize("text", ["see you at 10 a.m.", "Regards, AO", "Regards, A.O", "Regards, a.o.", "Regards, A O"])
def test_undotted_or_lowercase_initials_do_not_hold(text):
    assert "known_initials" not in check(text, REC_I)


ADDR = Record(names=(), case_sensitive=(), sequences=(), phrases=("ada.okafor", "112 Larkspur Road"), amounts=())


def test_phrases_are_word_bounded():
    assert "known_phrase" not in check("send to 1112 Larkspur Road", ADDR)
    got = check("write ada.okafor2@inboxly.co.uk", ADDR)
    assert "known_phrase" not in got and "email" in got


@pytest.mark.parametrize("text", ["at 112, Larkspur Road", "at 112  larkspur road", "at 112\nLarkspur Road",
                                  "login ada.okafor, thanks"])
def test_phrases_hold_across_punctuation_and_spacing(text):
    assert "known_phrase" in check(text, ADDR)


def test_control_passes():
    control()


def test_initials_do_not_span_a_sentence_break():
    rec = dataclasses.replace(REC, initials=("K", "I"))
    assert "known_initials" not in check("the U.K. I live", rec)
