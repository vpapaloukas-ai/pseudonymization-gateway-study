"""The three initials matchers (gateway, scanner, exit check) must agree on what is initials."""
import pytest
from helpers import make_customer

from pgw.exitcheck import check
from pgw.known import mask_known
from pgw.known_scan import occurrences
from pgw.pipeline import exit_record
from pgw.vault import Vault

ADA = make_customer()
UMAR = make_customer("Umar", "Kavanagh")


@pytest.mark.parametrize("c, text, expected", [
    (ADA, "A.O.", True), (ADA, "A. O.", True), (ADA, "A.O", False), (ADA, "AO", False), (ADA, "a.o.", False),
    (UMAR, "U.K.", False),
])
def test_the_three_modules_agree_on_initials(c, text, expected):
    msg = f"Regards, {text}"
    gateway = mask_known(msg, c, Vault())[0] != msg
    scanner = any(o.form == "initials" for o in occurrences(msg, c))
    exit_hit = "known_initials" in check(msg, exit_record(c))
    assert gateway == scanner == exit_hit == expected
