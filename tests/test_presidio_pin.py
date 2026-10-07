import json
from pathlib import Path

from pgw.presidio_probe import measure

SNAPSHOT = Path(__file__).resolve().parent.parent / "notes" / "presidio-defaults.json"


def test_presidio_matches_committed_snapshot(analyzer):
    assert measure(analyzer) == json.loads(SNAPSHOT.read_text(encoding="utf-8"))
