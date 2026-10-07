import json
from pathlib import Path

from presidio_analyzer import RecognizerResult

from pgw.detector import measure
from pgw.vault import TOKEN_RE, Vault

SNAPSHOT = Path(__file__).resolve().parent.parent / "notes" / "detector-configured.json"


def test_configuring_leaves_the_shipped_analyzer_alone(shipped, detector):
    shipped_entities = set(shipped.analyzer.get_supported_entities(language="en"))
    assert "UK_PHONE" not in shipped_entities and "AMOUNT" not in shipped_entities
    assert "UK_PHONE" in detector.entities


def test_organisations_and_dates_are_not_targets(detector):
    assert "DATE_TIME" not in detector.entities
    assert not any("ORG" in e for e in detector.entities)


def test_detections_overlapping_a_token_are_dropped_and_others_kept(detector, monkeypatch):
    text = "[CUSTOMER_1] Smith wrote from Whitby."

    def fake_analyze(text, **kwargs):
        return [RecognizerResult("PERSON", 0, 18, 0.9),      # spans the token and " Smith": dropped whole
                RecognizerResult("LOCATION", 30, 36, 0.9)]   # "Whitby", clear of tokens: applied

    monkeypatch.setattr(detector.analyzer, "analyze", fake_analyze)
    out = detector.mask(text, Vault())
    assert out.payload == "[CUSTOMER_1] Smith wrote from [LOCATION_1]."   # "Smith" left: the recorded limitation
    assert [d.entity_type for d in out.detections] == ["LOCATION"]


def test_custom_formats(detector):
    v = Vault()
    out = detector.mask("Call 07700 900456, ref BW-123456, £12.50, LA9 4RT, GB33 SYNT 1234 5612 3456 78.", v).payload
    types = {m.group(1) for m in TOKEN_RE.finditer(out)}
    assert {"UK_PHONE", "ORDER_NUMBER", "AMOUNT", "UK_POSTCODE", "IBAN_CODE"} <= types, out


def test_a_third_party_name_is_masked(detector):
    out = detector.mask("My husband John Smith placed it.", Vault()).payload
    assert "John" not in out


def test_dates_stay_in_clear(detector):
    out = detector.mask("Dispatched 2026-09-14, delivered on 18 September.", Vault()).payload
    assert "2026-09-14" in out and "18 September" in out


def test_matches_committed_snapshot(detector):
    assert measure(detector) == json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _inject(detector, monkeypatch, results):
    monkeypatch.setattr(detector.analyzer, "analyze", lambda text, **kwargs: list(results))


def test_an_exact_tie_goes_to_our_own_pattern_in_either_input_order(detector, monkeypatch):
    text = "Call 07700 900205 today."
    person = RecognizerResult("PERSON", 5, 17, 0.85)
    phone = RecognizerResult("UK_PHONE", 5, 17, 0.85)
    builtin_phone = RecognizerResult("PHONE_NUMBER", 5, 17, 0.75)
    for order in ([person, phone, builtin_phone], [phone, person, builtin_phone], [builtin_phone, person, phone],
                  [phone, builtin_phone, person]):
        _inject(detector, monkeypatch, order)
        assert detector.mask(text, Vault()).payload == "Call [UK_PHONE_1] today."


def test_an_exact_tie_between_two_built_ins_goes_to_the_alphabetically_first(detector, monkeypatch):
    text = "Ask Whitby now."
    a, b = RecognizerResult("PERSON", 4, 10, 0.85), RecognizerResult("LOCATION", 4, 10, 0.85)
    for order in ([a, b], [b, a]):
        _inject(detector, monkeypatch, order)
        assert detector.mask(text, Vault()).payload == "Ask [LOCATION_1] now."


def test_the_same_span_at_different_scores_keeps_the_higher(detector, monkeypatch):
    text = "Call 07700 900205 today."
    high, low = RecognizerResult("PERSON", 5, 17, 0.9), RecognizerResult("UK_PHONE", 5, 17, 0.85)
    for order in ([high, low], [low, high]):
        _inject(detector, monkeypatch, order)
        assert detector.mask(text, Vault()).payload == "Call [PERSON_1] today."


def test_detections_come_out_in_a_total_order_whatever_the_input_order(detector, monkeypatch):
    text = "Call 07700 900205 today."
    rs = [RecognizerResult("PERSON", 5, 17, 0.85), RecognizerResult("UK_PHONE", 5, 17, 0.85),
          RecognizerResult("PHONE_NUMBER", 5, 17, 0.75)]
    outs = set()
    for order in (rs, rs[::-1], [rs[1], rs[2], rs[0]], [rs[2], rs[0], rs[1]]):
        _inject(detector, monkeypatch, order)
        outs.add(tuple(detector.mask(text, Vault()).detections))
    assert len(outs) == 1
