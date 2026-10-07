"""Step 4 (spec §4): a separate pass over exactly what would be sent. It shares no code with known.py or
detector.py and imports nothing from this package: it is the verifier behind "0 of N", not a second chance.
check() returns the reasons to hold; an empty list means the message may leave."""
import re
from dataclasses import dataclass

TOKEN = re.compile(r"\[([A-Z][A-Z_]*)_(\d+)\]")
HIGH_RISK_TOKENS = frozenset({"CREDIT_CARD", "IBAN_CODE"})
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
PHONE = re.compile(r"(?<!\d)(?:(?:\+|00)\s?44\s?(?:\(0\)\s?)?|0)\d{2,4}[\s.-]?\d{3,4}[\s.-]?\d{3,4}(?!\d)")
DIGIT_RUN = re.compile(r"\d(?:[^\S\n]{0,2}\d){7,}")   # 8+ digits, contiguous or joined by 1-2 non-newline spaces (incl. nbsp); "-", "/" and "." stay out: dates use them
CARD = re.compile(r"(?<!\d)\d(?:[\s.-]{0,2}\d){12,18}(?!\d)")
IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]){11,30}\b")
NINO = re.compile(r"\b[A-Z]{2} ?\d{2} ?\d{2} ?\d{2} ?[A-D]\b")   # broad on purpose: QQ is the published example
HOLD_GROUPS = {"high_risk_token": "high_risk", "card": "high_risk", "iban": "high_risk", "nino": "high_risk",
               "email": "leftover_pattern", "phone": "leftover_pattern", "digit_run": "leftover_pattern",
               "known_name": "known_value", "known_number": "known_value", "known_phrase": "known_value",
               "known_amount": "known_value", "known_initials": "known_value"}


@dataclass(frozen=True)
class Record:
    """The sender's fields as plain strings, so this module needs nothing from the CRM's types."""
    names: tuple[str, ...]            # first name, surname
    case_sensitive: tuple[str, ...]   # names that are also ordinary words: matched only as written
    sequences: tuple[str, ...]        # phone, account, IBAN, postcode, order numbers, digit-only forms
    phrases: tuple[str, ...]          # email address, its local part, street line
    amounts: tuple[int, ...]          # pence
    initials: tuple[str, ...] = ()    # first and surname initial: matched dotted and uppercase only ("A.O.", "A. O.")


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def _iban_ok(s: str) -> bool:
    s = s.replace(" ", "")
    return 15 <= len(s) <= 34 and int("".join(str(int(c, 36)) for c in s[4:] + s[:4])) % 97 == 1


def _spaced(s: str) -> re.Pattern:
    chars = re.sub(r"[^A-Za-z0-9]", "", s)
    return re.compile(r"(?<![A-Za-z0-9])" + r"[\s\-.]*".join(map(re.escape, chars)) + r"(?![A-Za-z0-9])",
                      re.IGNORECASE)


def _amount_found(text: str, pence: int) -> bool:
    pounds, p = divmod(pence, 100)
    for m in re.finditer(r"(£\s?)?(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{2}))?(?!\d|\.\d)", text):
        if (m.group(1) or m.group(3)) and int(m.group(2).replace(",", "")) == pounds and int(m.group(3) or 0) == p:
            return True
    return False


def _known(bare: str, rec: Record) -> set[str]:
    found = set()
    for n in rec.names:
        flags = 0 if n in rec.case_sensitive else re.IGNORECASE
        if re.search(r"(?<![\w])" + re.escape(n) + r"(?![\w])", bare, flags):
            found.add("known_name")
    for s in rec.sequences:
        digits = re.sub(r"\D", "", s)
        if _spaced(s).search(bare) or (s.startswith("0") and len(digits) >= 10 and _spaced("44" + digits[1:]).search(bare)):
            found.add("known_number")
    if any(re.search(r"(?<![\w])" + r"\W{1,3}".join(re.escape(w) for w in ph.split()) + r"(?![\w])", bare,
                     re.IGNORECASE) for ph in rec.phrases):
        found.add("known_phrase")
    if any(_amount_found(bare, p) for p in rec.amounts):
        found.add("known_amount")
    if len(rec.initials) == 2:
        F, L = map(re.escape, rec.initials)
        if re.search(rf"(?<![A-Za-z]){F}\.\s*{L}\.(?![A-Za-z])", bare):
            found.add("known_initials")
    return found


def check(message: str, rec: Record | None) -> list[str]:
    reasons: set[str] = set()
    if {m.group(1) for m in TOKEN.finditer(message)} & HIGH_RISK_TOKENS:
        reasons.add("high_risk_token")
    bare = TOKEN.sub(" ", message)
    if any(_luhn(re.sub(r"\D", "", m.group(0))) for m in CARD.finditer(bare)):
        reasons.add("card")
    if any(_iban_ok(m.group(0)) for m in IBAN.finditer(bare.upper())):
        reasons.add("iban")
    if NINO.search(bare.upper()):
        reasons.add("nino")
    if EMAIL.search(bare):
        reasons.add("email")
    if PHONE.search(bare):
        reasons.add("phone")
    if DIGIT_RUN.search(bare):
        reasons.add("digit_run")
    if rec is not None:
        reasons |= _known(bare, rec)
    return sorted(reasons)


def control() -> None:
    """Positive controls run inside every pipeline run (spec §7): a check that misses these tests nothing."""
    rec = Record(("Ada", "Okafor"), (), ("07700 900123",), (), ())
    assert "known_number" in check("call 07700 900123", rec), "exit check missed a known phone number"
    assert "known_name" in check("Okafor", rec), "exit check missed a known surname"
    assert "card" in check("4111 1111 1111 1111", None), "exit check missed a raw card number"
    initials = Record(("Ada", "Okafor"), (), (), (), (), ("A", "O"))
    assert "known_initials" in check("Regards, A.O.", initials), "exit check missed the sender's initials"
    assert check("placed 2026-09-14 [ORDER_1]", rec) == [], "exit check held a clean message"
