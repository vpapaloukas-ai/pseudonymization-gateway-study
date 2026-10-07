from pgw.vault import TOKEN_RE, Vault, restore


def test_same_value_same_token():
    v = Vault()
    assert v.token("PERSON", "Ada Okafor") == "[PERSON_1]" == v.token("PERSON", "Ada Okafor")


def test_numbering_is_per_type():
    v = Vault()
    assert v.token("PERSON", "Ada Okafor") == "[PERSON_1]"
    assert v.token("PERSON", "Ben Hale") == "[PERSON_2]"
    assert v.token("LOCATION", "Whitby") == "[LOCATION_1]"


def test_key_is_the_exact_string():
    v = Vault()
    assert v.token("PERSON", "Ada Okafor") != v.token("PERSON", "ada okafor")


def test_token_re_parses_underscored_types():
    assert TOKEN_RE.fullmatch("[EMAIL_ADDRESS_12]").groups() == ("EMAIL_ADDRESS", "12")


def test_json_round_trip_keeps_numbering():
    v = Vault()
    v.token("PERSON", "Ada Okafor")
    v.token("PERSON", "Ben Hale")
    w = Vault.from_json(v.to_json())
    assert w.tokens() == v.tokens()
    assert w.token("PERSON", "Cara Diaz") == "[PERSON_3]"


def test_from_json_across_types_and_restore_from_a_loaded_vault():
    v = Vault()
    v.token("PERSON", "Ada Okafor")
    v.token("LOCATION", "Whitby")
    v.token("PERSON", "Ben Hale")
    v.token("EMAIL_ADDRESS", "ada.okafor@harrowfield-logistics.co.uk")
    w = Vault.from_json(v.to_json())
    assert w.token("LOCATION", "Ludlow") == "[LOCATION_2]"
    assert w.token("EMAIL_ADDRESS", "ben.hale@harrowfield-logistics.co.uk") == "[EMAIL_ADDRESS_2]"
    assert w.token("PERSON", "Cara Diaz") == "[PERSON_3]"
    assert restore("[PERSON_2] met [PERSON_1] in [LOCATION_1].", w) == "Ben Hale met Ada Okafor in Whitby."


def test_restore_leaves_unknown_tokens():
    assert restore("[PERSON_9] agreed", Vault()) == "[PERSON_9] agreed"


def test_restore_inside_markdown_and_possessive():
    v = Vault()
    v.token("PERSON", "Ada Okafor")
    assert restore("**[PERSON_1]**'s plan", v) == "**Ada Okafor**'s plan"
