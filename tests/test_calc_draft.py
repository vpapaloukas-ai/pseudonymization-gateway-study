import pytest

from pgw import calc, draftcheck
from pgw.vault import Vault, restore


def vault():
    v = Vault()
    v.token("CUSTOMER", "Ada Okafor")
    v.token("FIRST_NAME", "Ada")
    v.token("AMOUNT", "£45.00")
    v.token("AMOUNT", "£65.00")
    v.token("AMOUNT", "£ 12.5")      # a detected value that is not a clean figure
    v.token("ORDER", "BW-1")
    return v


def post(raw):
    v = vault()
    text, figures, bad = calc.apply(raw, v)
    restored = restore(text, v)
    return restored, draftcheck.check(raw, restored, v)


def test_a_first_name_token_in_a_reply_is_clean():
    assert post("Hi [FIRST_NAME_1], we will refund [AMOUNT_1].") == ("Hi Ada, we will refund £45.00.", [])


def test_pence():
    assert calc.pence("£1,234.56") == 123456 and calc.pence("£45") == 4500 and calc.pence("£ 45.00") == 4500
    with pytest.raises(ValueError):
        calc.pence("45")


def test_sum_and_diff_are_computed_locally():
    assert post("Refund {SUM: [AMOUNT_1], [AMOUNT_2]} today.") == ("Refund £110.00 today.", [])
    assert post("Difference {DIFF: [AMOUNT_2], [AMOUNT_1]}.") == ("Difference £20.00.", [])
    assert post("{ SUM : [AMOUNT_1] ,[AMOUNT_2] , [AMOUNT_1] }")[0] == "£155.00"


def test_a_clean_reply_passes():
    assert post("Dear [CUSTOMER_1], we will refund [AMOUNT_1] within 3-5 working days.") == (
        "Dear Ada Okafor, we will refund £45.00 within 3-5 working days.", [])


@pytest.mark.parametrize("raw, reason", [
    ("Dear [CUSTOMER_2]", "invented_token"),
    ("Dear [CUSTOMER]", "malformed_token"),
    ("Dear CUSTOMER_1", "malformed_token"),
    ("Dear [Customer 1]", "malformed_token"),
    ("Refund {MUL: [AMOUNT_1], [AMOUNT_2]}", "bad_expression"),
    ("Refund {SUM: [AMOUNT_1], [AMOUNT_9]}", "bad_expression"),
    ("Refund {DIFF: [AMOUNT_1], [AMOUNT_2]}", "bad_expression"),
    ("Refund £99.00", "bare_amount"),
])
def test_draft_holds(raw, reason):
    assert reason in post(raw)[1]


def test_invented_token_is_also_leftover_after_restore():
    assert set(post("Dear [CUSTOMER_2]")[1]) >= {"invented_token", "leftover_token"}


def test_a_figure_from_a_calculation_or_token_is_allowed():
    assert post("Total {SUM: [AMOUNT_1], [AMOUNT_2]}, of which [AMOUNT_1] for the lamp.")[1] == []


def test_lowercase_brackets_are_prose_not_tokens():
    assert post("Dear [CUSTOMER_1], the label said [sic] fragile.")[1] == []


@pytest.mark.parametrize("raw, reason", [
    ("{SUM: [AMOUNT_1], [AMOUNT_2]", "bad_expression"),
    ("SUM: [AMOUNT_1], [AMOUNT_2]}", "bad_expression"),
    ("{SUM: [AMOUNT_1], {SUM: [AMOUNT_1], [AMOUNT_2]}}", "bad_expression"),
    ("{{SUM: [AMOUNT_1], [AMOUNT_2]}}", "bad_expression"),
    ("Refund of £65.00 and also [AMOUNT_1].", "bare_amount"),
    ("Total {SUM: [AMOUNT_1], [AMOUNT_2]} (£110.00).", "bare_amount"),
    ("refund £45.5", "bare_amount"),
    ("refund £45.0", "bare_amount"),
    ("refund £.99", "bare_amount"),
    ("refund £  99", "bare_amount"),
    ("refund ￡99.00", "bare_amount"),
    ("refund 99 GBP", "bare_amount"),
    ("refund GBP 99", "bare_amount"),
    ("refund 99 pounds", "bare_amount"),
    ("£[AMOUNT_1]", "bare_amount"),
])
def test_provenance_holds(raw, reason):
    assert reason in post(raw)[1]


def test_a_non_canonical_token_value_is_not_held():
    assert post("Refund [AMOUNT_3] today.") == ("Refund £ 12.5 today.", [])


@pytest.mark.parametrize("raw", ["Refund [AMOUNT_a] for [ORDER_1].", "Refund [AMOUNT_n]."])
def test_a_letter_in_place_of_the_number_is_malformed(raw):
    assert "malformed_token" in post(raw)[1]


def test_a_literal_example_expression_is_held():
    reasons = post("Refund {SUM: [AMOUNT_a], [AMOUNT_b]} today.")[1]
    assert reasons and "bad_expression" in reasons and "malformed_token" in reasons


def test_prose_with_underscores_and_brackets_is_not_malformed():
    assert post("NHS_1 and VAT_20 apply, see [VAT] and [Step 1].")[1] == []


@pytest.mark.parametrize("raw", ["Hi [first_name_1], re [ORDER_1].", "Re [Order_1].", "Refund [amount_2]."])
def test_a_vault_token_in_the_wrong_case_is_malformed(raw):
    assert "malformed_token" in post(raw)[1]


def test_the_exact_uppercase_token_and_a_type_not_in_the_vault_are_not_malformed():
    assert post("Hi [FIRST_NAME_1], re [ORDER_1].")[1] == []
    assert "malformed_token" not in post("See [step_1] and [Step_2].")[1]


def test_control_passes():
    draftcheck.control()
