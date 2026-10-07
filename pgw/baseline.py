"""Presidio AS SHIPPED, for the contrast row only (spec §1, §6): AnalyzerEngine() with no arguments, no custom
recognisers, no threshold, plus one custom operator that writes [TYPE_n] tokens into the vault.

The anonymizer calls the custom operator with the entity's text only (operators/custom.py at 2.2.364), and
it may first merge neighbouring same-type entities, so tokens are assigned inside the operator, one operator
per entity type."""
from functools import partial

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from pgw.masking import Detection, Masked
from pgw.vault import Vault


class ShippedGateway:
    def __init__(self) -> None:
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()
        self.entities = sorted(self.analyzer.get_supported_entities(language="en"))

    def mask(self, text: str, vault: Vault) -> Masked:
        results = self.analyzer.analyze(text=text, language="en")
        detections = tuple(sorted((Detection(r.entity_type, r.start, r.end, r.score) for r in results),
                                  key=lambda d: (d.start, d.end)))
        operators = {e: OperatorConfig("custom", {"lambda": partial(vault.token, e)}) for e in self.entities}
        operators["DEFAULT"] = OperatorConfig("custom", {"lambda": partial(vault.token, "PII")})
        out = self.anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)
        return Masked(out.text, detections)
