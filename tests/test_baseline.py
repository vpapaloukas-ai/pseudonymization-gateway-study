from pgw.vault import TOKEN_RE, Vault, restore


def test_entity_names_make_parseable_tokens(shipped):
    for e in shipped.entities:
        assert TOKEN_RE.fullmatch(f"[{e}_1]"), e


def test_round_trip_one_text(shipped):
    text = "Ada Okafor met Ben Hale in Whitby. Email ada.okafor@harrowfield-logistics.co.uk."
    v = Vault()
    m = shipped.mask(text, v)
    assert m.payload != text
    assert restore(m.payload, v) == text


def test_masking_is_deterministic(shipped):
    text = "John Smith emailed Jane Doe from Ludlow."
    assert shipped.mask(text, Vault()).payload == shipped.mask(text, Vault()).payload


def test_detections_are_sorted_and_inside_the_text(shipped):
    text = "John Smith emailed Jane Doe from Ludlow."
    m = shipped.mask(text, Vault())
    assert "PERSON" in {d.entity_type for d in m.detections}
    assert list(m.detections) == sorted(m.detections, key=lambda d: (d.start, d.end))
    assert all(0 <= d.start < d.end <= len(text) for d in m.detections)
