"""The audit (spec §3): two instruments that share no code with the gateway find what the generator wrote
beyond the plants. A pattern scan, and a separate Opus pass that lists every name, number and address.
Anything unplanned becomes gold, marked with its kind, and is scored like everything else."""
import re
from dataclasses import dataclass

from pgw import known_scan, names
from pgw.briefs import Brief
from pgw.crm import Customer

AUDIT_EFFORT = "medium"
KINDS = ("name", "email", "phone", "address", "postcode", "account", "order", "card", "bank", "amount", "other")
AUDIT_SYSTEM = f"""You audit a synthetic customer email for personal and payment details. List every person's name (full or partial, including nicknames and initials), email address, phone number, postal address or part of one (street, town, postcode), account or order number, card number, bank detail and money amount that appears in the email. Copy each exactly as it appears. Do not list the company name "{names.COMPANY}" or product names. Return JSON with "items", a list of objects with "kind" and "text"."""
AUDIT_SCHEMA = {"type": "json_schema", "schema": {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {"kind": {"type": "string", "enum": list(KINDS)}, "text": {"type": "string"}},
        "required": ["kind", "text"], "additionalProperties": False}}},
    "required": ["items"], "additionalProperties": False}}
PATTERNS = (
    ("email", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"),
    ("phone", r"(?:\+44\s?|0)7\d{3}[\s-]?\d{3}[\s-]?\d{3}"),
    ("amount", r"£\s?\d[\d,]*(?:\.\d{2})?"),
    ("card", r"\b\d{4}[ -]?\d{4,6}[ -]?\d{4,5}(?:[ -]?\d{4})?\b"),
    ("bank", r"\bGB\d{2}(?: ?[A-Z0-9]{4}){4,5}(?: ?[A-Z0-9]{1,4})?\b"),
    ("postcode", r"\b[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}\b"),
    ("order", r"\bBW-?\d{6}\b"),
)


@dataclass(frozen=True)
class GoldItem:
    kind: str
    value: str
    parts: tuple[str, ...]
    origin: str          # planted | record_scan | audit
    known: bool
    listed: bool
    high_risk: bool


def pattern_scan(text: str) -> list[tuple[str, str]]:
    return [(kind, m.group(0)) for kind, rx in PATTERNS for m in re.finditer(rx, text)]


def _norm(s: str) -> str:
    s = re.sub(r"['’]s\b", "", s)
    return re.sub(r"[^a-z0-9£]", "", s.lower())


def _words(s: str) -> tuple[str, ...]:
    s = re.sub(r"['’]s\b", "", s)
    return tuple(re.findall(r"[a-z0-9£]+", s.lower()))


def _covered(value: str, sources: list[str]) -> bool:
    n, w = _norm(value), _words(value)
    for s in sources:
        sw = _words(s)
        if n == _norm(s) or (w and any(w == sw[i:i + len(w)] for i in range(len(sw) - len(w) + 1))):
            return True
    return False


def build_gold(b: Brief, text: str, audit_items: list[dict], c: Customer) -> list[GoldItem]:
    scan = known_scan.occurrences(text, c)
    scan_texts = [o.text for o in scan]
    for p in b.plants:
        if p.known:
            assert _covered(p.value, scan_texts), f"{b.email_id}: planted known value {p.value!r} not found by the scan"
    gold = [GoldItem(p.kind, p.value, p.parts, "planted", p.known, p.listed, p.high_risk)
            for p in b.plants if not p.known]
    gold += [GoldItem(f"record:{o.field}:{o.form}", o.text, (o.text,), "record_scan", True, o.listed, False)
             for o in scan]
    sources = [v for p in b.plants for v in (p.value, *p.parts)] + [o.text for o in scan]
    sources += [names.COMPANY] + [n for n, _ in names.PRODUCTS]
    seen: set[str] = set()
    for kind, value in pattern_scan(text) + [(i["kind"], i["text"]) for i in audit_items]:
        n = _norm(value)
        if not n or n in seen:
            continue
        seen.add(n)
        if _covered(value, sources):
            gold.append(GoldItem(f"skipped:{kind}", value, (value,), "skipped", False, False, False))
        else:
            gold.append(GoldItem(f"unplanned:{kind}", value, (value,), "audit", False, False,
                                 _valid_card(value) if kind == "card" else _valid_iban(value) if kind == "bank" else False))
    return gold


def _valid_card(value: str) -> bool:
    d = re.sub(r"\D", "", value)
    if not 13 <= len(d) <= 19:
        return False
    total = 0
    for i, ch in enumerate(reversed(d)):
        n = int(ch)
        if i % 2 == 1:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def _valid_iban(value: str) -> bool:
    s = re.sub(r"\s", "", value).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", s):
        return False
    return int("".join(str(int(ch, 36)) for ch in s[4:] + s[:4])) % 97 == 1
