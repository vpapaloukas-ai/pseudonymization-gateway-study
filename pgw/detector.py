"""Step 3 (spec §4): Presidio 2.2.364, CONFIGURED, as backup for what the record does not hold. It has its
own registry, so the shipped baseline (pgw/baseline.py) is never altered. Organisations stay in clear (GDPR
Recital 14; the reply needs courier and bank names), and dates stay in clear (spec §5).

usage: python -m pgw.detector notes/detector-configured.json
"""
import json
import sys
from functools import partial
from pathlib import Path

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from pgw.masking import Detection, Masked
from pgw.vault import TOKEN_RE, Vault

BUILT_IN = ("PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "LOCATION", "IBAN_CODE", "CREDIT_CARD")
CUSTOM = (
    ("UK_PHONE", r"(?<![\d+])(?:(?:\+|00)\s?44\s?(?:\(0\)\s?)?|0)7\d{3}[\s-]?\d{3}[\s-]?\d{3}(?!\d)", 0.85),
    ("IBAN_CODE", r"\bGB\d{2}\s?[A-Z]{4}(?:\s?\d{4}){3}\s?\d{2}\b", 0.85),
    ("ORDER_NUMBER", r"\bBW-?\s?\d{6}\b", 0.85),
    ("ACCOUNT_NUMBER", r"\bBWC\s?\d{7}\b", 0.85),
    ("AMOUNT", r"£\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?(?!\d)", 0.85),
    ("UK_POSTCODE", r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b", 0.6),
)
_CUSTOM_TYPES = frozenset(e for e, _, _ in CUSTOM)
THRESHOLD = 0.4   # fixed on the dev batch before the freeze (spec §4 step 3); a change is a dev-run ruling
PROBES = (
    "My husband John Smith placed it from Whitby.",
    "Call 07700 900456 or +44 7700 900457.",
    "Ref BW-123456, account BWC7654321, £12.50 and £1,200.",
    "Send it to 4 Mill Lane, Kendal LA9 4RT.",
    "Refund to GB33 SYNT 1234 5612 3456 78 or card 4111 1111 1111 1111.",
    "Dispatched 2026-09-14 by Harrowfield Logistics Ltd.",
)


def _resolve_ties(results: list) -> list:
    """Presidio hands results over in an order that varies between processes (it builds them through set()), and
    its anonymizer keeps the LAST of two same-span same-score results (has_conflict drops an equal-span result whose
    score is <= a later one's). So the tie is settled here, by rule: per
    exact (start, end) keep the highest score; at equal score prefer our own entity types over built-ins, then the
    alphabetically first entity_type. What is returned has a total order (start, end, -score, entity_type)."""
    best: dict = {}
    for r in results:
        key = (r.start, r.end)
        rank = (-r.score, r.entity_type not in _CUSTOM_TYPES, r.entity_type)
        if key not in best or rank < best[key][0]:
            best[key] = (rank, r)
    return sorted((r for _, r in best.values()), key=lambda r: (r.start, r.end, -r.score, r.entity_type))


class ConfiguredDetector:
    def __init__(self, nlp_engine=None) -> None:
        if nlp_engine is None:
            self.analyzer = AnalyzerEngine()
        else:
            registry = RecognizerRegistry()
            registry.load_predefined_recognizers(languages=["en"])
            self.analyzer = AnalyzerEngine(registry=registry, nlp_engine=nlp_engine, supported_languages=["en"])
        for entity, regex, score in CUSTOM:
            self.analyzer.registry.add_recognizer(PatternRecognizer(
                supported_entity=entity, name=f"pgw_{entity.lower()}",
                patterns=[Pattern(name=entity.lower(), regex=regex, score=score)]))
        self.anonymizer = AnonymizerEngine()
        self.entities = sorted(set(BUILT_IN) | {e for e, _, _ in CUSTOM})

    def mask(self, text: str, vault: Vault) -> Masked:
        taken = [(m.start(), m.end()) for m in TOKEN_RE.finditer(text)]
        results = [r for r in self.analyzer.analyze(text=text, language="en", entities=self.entities,
                                                    score_threshold=THRESHOLD)
                   if all(r.end <= s or r.start >= e for s, e in taken)]
        detections = tuple(sorted((Detection(r.entity_type, r.start, r.end, r.score) for r in results),
                                  key=lambda d: (d.start, d.end, d.entity_type, d.score)))
        operators = {e: OperatorConfig("custom", {"lambda": partial(vault.token, e)}) for e in self.entities}
        operators["DEFAULT"] = OperatorConfig("custom", {"lambda": partial(vault.token, "PII")})
        out = self.anonymizer.anonymize(text=text, analyzer_results=_resolve_ties(results), operators=operators)
        return Masked(out.text, detections)


def measure(det: ConfiguredDetector) -> dict:
    return {"entities": det.entities, "threshold": THRESHOLD,
            "probes": [{"text": t, "masked": det.mask(t, Vault()).payload} for t in PROBES]}


if __name__ == "__main__":
    Path(sys.argv[1]).write_text(json.dumps(measure(ConfiguredDetector()), indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8", newline="\n")
