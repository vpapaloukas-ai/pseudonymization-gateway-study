"""Step 7 (spec §4): the draft is held if it carries an invented, leftover or malformed token, an expression
outside the two forms, or a money amount that did not come from a token or a calculation. Figures are judged by
PROVENANCE, not value: after calc.apply and before restore, every legitimate figure is still a token or a
computed result, so any other "£" (or a worded amount) was typed by the model. Other numbers ("3-5 working
days", dates) are allowed."""
import re

from pgw.calc import apply
from pgw.vault import TOKEN_RE, Vault, restore

POUND = re.compile(r"[£￡]")
WORDED = re.compile(r"\d[\d,.]*\s*(?:GBP|pounds?)\b|\bGBP\s*\d", re.IGNORECASE)
LEFTOVER_EXPR = re.compile(r"[{}]|\b(?:SUM|DIFF)\s*:", re.IGNORECASE)


def _malformed(restored: str, types: set[str]) -> bool:
    """Wrong-format variants of the token types this vault actually holds: [TYPE], [TYPE 1], [TYPE-1], TYPE_1,
    and [TYPE_x] where x is anything but the number alone ([AMOUNT_a], [AMOUNT_n]); and a well-shaped [TYPE_1]
    whose type is written in the wrong case ([first_name_1], [Order_1]) - built only from the vault's own types."""
    for t in types:
        n = re.escape(t)
        if any(m.group(0) != m.group(0).upper() for m in re.finditer(rf"\[{n}_\d+\]", restored, re.IGNORECASE)):
            return True
        if re.search(rf"\[{n}\]|\[{n}[ -]\d+\]|(?<![\[\w]){n}_\d+\b(?!\])|\[{n}_(?!\d+\])[^\]]*\]", restored,
                     re.IGNORECASE):
            return True
    return False


def check(raw: str, restored: str, vault: Vault) -> list[str]:
    reasons = set()
    if any(vault.value(m.group(0)) is None for m in TOKEN_RE.finditer(raw)):
        reasons.add("invented_token")
    if TOKEN_RE.search(restored):
        reasons.add("leftover_token")
    if _malformed(restored, {TOKEN_RE.fullmatch(t).group(1) for t in vault.tokens()}):
        reasons.add("malformed_token")
    calculated, figures, bad = apply(raw, vault)
    if bad or LEFTOVER_EXPR.search(calculated):
        reasons.add("bad_expression")
    rest = calculated
    for f in figures:
        rest = rest.replace(f, " ", 1)
    if POUND.search(rest) or WORDED.search(rest):
        reasons.add("bare_amount")
    return sorted(reasons)


def control() -> None:
    """Positive control run inside every pipeline run (spec §7)."""
    v = Vault()
    v.token("CUSTOMER", "Ada Okafor")
    v.token("AMOUNT", "£45.00")
    v.token("AMOUNT", "£65.00")
    for raw, expected in (("Dear [CUSTOMER_9], {MUL: [AMOUNT_1]} and £5.00.",
                           {"invented_token", "leftover_token", "bad_expression", "bare_amount"}),
                          ("Refund of £65.00 and [AMOUNT_1].", {"bare_amount"}),
                          ("{SUM: [AMOUNT_1], [AMOUNT_2]", {"bad_expression"})):
        text, _, _ = apply(raw, v)
        got = set(check(raw, restore(text, v), v))
        assert expected <= got, f"draft check missed {expected - got} in {raw!r}"
