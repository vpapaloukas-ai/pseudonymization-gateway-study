"""What Presidio as shipped detects on fixed probe sentences, and which spaCy model it loaded.

usage: python -m pgw.presidio_probe notes/presidio-defaults.json
"""
import json
import sys
from pathlib import Path

PROBES = (
    "John Doe met Jane Smith in Whitby on 3 March.",
    "ACME Corp paid $154,000 to Harrowfield Logistics Ltd.",
    "Email ada.okafor@harrowfield-logistics.co.uk or call 07700 900123.",
    "Pay GB82 WEST 1234 5698 7654 32 or GB82WEST12345698765432 by Friday.",
    "Her salary is £54,500, about 54.5k a year.",
    "the review is with rose and mark, and Will signs off.",
)


def measure(analyzer) -> dict:
    nlp = getattr(analyzer.nlp_engine, "nlp", None) or {}
    model = nlp.get("en")
    meta = dict(model.meta) if model is not None else {}
    out = {
        "spacy_model": f"{meta.get('lang', '?')}_{meta.get('name', '?')}",
        "spacy_model_version": meta.get("version", "?"),
        "supported_entities": sorted(analyzer.get_supported_entities(language="en")),
        "probes": [],
    }
    for text in PROBES:
        found = sorted({(r.entity_type, text[r.start:r.end]) for r in analyzer.analyze(text=text, language="en")})
        out["probes"].append({"text": text, "found": [list(x) for x in found]})
    return out


if __name__ == "__main__":
    from presidio_analyzer import AnalyzerEngine

    data = measure(AnalyzerEngine())
    Path(sys.argv[1]).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
