import pytest
from helpers import make_customer

from pgw.known import mask_known
from pgw.vault import TOKEN_RE, Vault, restore

ADA = make_customer()


def masked(text, c=ADA):
    return mask_known(text, c, Vault())[0]


@pytest.mark.parametrize("text", ["Ada Okafor", "Okafor", "Ms Okafor", "Ms. Okafor", "A.O.", "A. O."])
def test_every_full_name_form_is_one_customer_token(text):
    assert masked(f"Regards, {text}") == "Regards, [CUSTOMER_1]"


@pytest.mark.parametrize("text", ["Ada", "ada"])
def test_the_first_name_alone_is_a_first_name_token(text):
    assert masked(f"Regards, {text}") == "Regards, [FIRST_NAME_1]"


def test_the_first_name_restores_alone():
    v = Vault()
    out = mask_known("Thanks, Ada", ADA, v)[0]
    assert restore(out, v) == "Thanks, Ada"
    out = mask_known("Thanks, Ada Okafor", ADA, v)[0]
    assert restore(out, v) == "Thanks, Ada Okafor"


@pytest.mark.parametrize("text", ["AO", "A O", "A.O", "a.o.", "a. o."])
def test_undotted_and_lowercase_initials_are_not_masked(text):
    assert masked(f"Regards, {text}") == f"Regards, {text}"


def test_possessive_keeps_its_suffix():
    assert masked("Ada's lamp") == "[FIRST_NAME_1]'s lamp"


def test_email_beats_the_name_inside_it():
    assert masked("write to ada.okafor@postbox-mail.co.uk") == "write to [EMAIL_1]"
    assert masked("my login is ada.okafor") == "my login is [EMAIL_1]"


@pytest.mark.parametrize("text", ["07700 900123", "07700900123", "07700-900-123", "+44 7700 900123",
                                  "+44 (0)7700 900123", "0044 7700 900123", "(07700) 900123", "447700900123", "44 7700 900123"])
def test_phone_formats(text):
    assert masked(f"call {text} today") == "call [PHONE_1] today"


@pytest.mark.parametrize("text, token", [("BW-482913", "[ORDER_1]"), ("bw482913", "[ORDER_1]"),
                                         ("BW 482913", "[ORDER_1]"), ("482913", "[ORDER_1]"),
                                         ("BWC1234567", "[ACCOUNT_1]"), ("1234567", "[ACCOUNT_1]")])
def test_order_and_account_numbers(text, token):
    assert masked(f"ref {text}.") == f"ref {token}."


def test_iban_spaced_and_unspaced():
    spaced = " ".join(ADA.iban[i:i + 4] for i in range(0, len(ADA.iban), 4))
    assert masked(f"pay {ADA.iban}") == masked(f"pay {spaced}") == "pay [IBAN_1]"


def test_address_parts():
    assert masked("I live at 12 larkspur road, Whitby YO21 3XX") == "I live at [ADDRESS_1], Whitby [POSTCODE_1]"
    assert masked("postcode yo213xx") == "postcode [POSTCODE_1]"


@pytest.mark.parametrize("text", ["£45.00", "£45", "£ 45.00", "45.00"])
def test_known_amounts(text):
    assert TOKEN_RE.fullmatch(masked(text))


@pytest.mark.parametrize("text", ["45 minutes", "45.50", "£450.00", "1450.00"])
def test_amount_lookalikes_stay(text):
    assert masked(text) == text


def test_word_name_matches_only_when_capitalised():
    will = make_customer("Will", "Hale")
    assert masked("Will here: will you refund it?", will) == "[FIRST_NAME_1] here: will you refund it?"


def test_other_people_are_untouched():
    assert masked("Ben Hale and Ruth Ingram") == "Ben Hale and Ruth Ingram"


def test_vault_is_seeded_with_every_field_and_restores_canonical_values():
    v = Vault()
    out, hits = mask_known("call 07700900123 about 482913", ADA, v)
    values = set(v.tokens().values())
    assert {ADA.full, ADA.first, ADA.email, ADA.phone, ADA.account, ADA.iban, ADA.street, ADA.postcode,
            "BW-482913", "BW-500001", "£45.00", "£65.00", "£110.00", "£120.00"} <= values
    assert restore(out, v) == "call 07700 900123 about BW-482913"
    assert [h.start for h in hits] == sorted(h.start for h in hits)


def test_hits_do_not_overlap():
    _, hits = mask_known("Ada Okafor, ada.okafor@postbox-mail.co.uk, 07700 900123", ADA, Vault())
    for a, b in zip(hits, hits[1:]):
        assert a.end <= b.start


def test_lowercase_undotted_initials_stay():
    assert masked("ao and a o") == "ao and a o"


def test_initials_never_eat_an_order_prefix():
    ben = make_customer("Ben", "Wainwright")
    assert masked("order BW-123456 and BW123456", ben) == "order BW-123456 and BW123456"


@pytest.mark.parametrize("text, expected", [
    ("Ada\nOkafor.", "[CUSTOMER_1]."),
    ("(Ada Okafor)", "([CUSTOMER_1])"),
    ("BW-482913, thanks", "[ORDER_1], thanks"),
    ("£45.00.", "[AMOUNT_1]."),
    ("OKAFOR", "[CUSTOMER_1]"),
])
def test_punctuation_and_newlines(text, expected):
    assert masked(text) == expected


def test_initials_never_span_a_sentence_break():
    kieran = make_customer("Kieran", "Ingram")
    assert masked("I live in the U.K. I love it", kieran) == "I live in the U.K. I love it"
    alistair = make_customer("Alistair", "Iqbal")
    assert masked("Option A. I think so.", alistair) == "Option A. I think so."


def test_abbreviation_initials_get_no_form():
    umar = make_customer("Umar", "Kavanagh")
    assert masked("shipping to the U.K. today", umar) == "shipping to the U.K. today"
