"""Step 2 (spec §4): mask what the company knows. The vault is filled from the sender's CRM record and the
listed variants. Every form of a field maps to ONE token; restore puts back the canonical value."""
import re
from dataclasses import dataclass

from pgw import names
from pgw.crm import Customer, money
from pgw.vault import Vault

SEP = r"[\s\-.()]*"


@dataclass(frozen=True)
class Form:
    entity: str
    canonical: str
    pattern: re.Pattern


@dataclass(frozen=True)
class Hit:
    entity: str
    start: int
    end: int
    text: str
    token: str


def _alnum(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", s)


def _seq(chars: str) -> str:
    return r"(?<![A-Za-z0-9])" + SEP.join(re.escape(ch) for ch in chars) + r"(?![A-Za-z0-9])"


def _words(phrase: str) -> str:
    return r"(?<![\w])" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"(?![\w])"


def amount_regex(pence: int) -> str:
    pounds, p = divmod(pence, 100)
    whole = f"{pounds:,}".replace(",", ",?")
    end = r"(?!\d|\.\d)"
    if p:
        return rf"(?:£\s?)?(?<![\d.,]){whole}\.{p:02d}{end}"
    return rf"£\s?{whole}(?:\.00)?{end}|(?<![\d.,£]){whole}\.00{end}"


def forms(c: Customer) -> list[Form]:
    out: list[Form] = []

    def add(entity: str, canonical: str, regex: str, case_sensitive: bool = False) -> None:
        out.append(Form(entity, canonical, re.compile(regex, 0 if case_sensitive else re.IGNORECASE)))

    local = c.email.split("@")[0]
    add("EMAIL", c.email, re.escape(c.email))
    add("EMAIL", c.email, r"(?<![\w.])" + re.escape(local) + r"(?![\w])")
    for phrase in (c.full, f"{c.title} {c.last}", f"{c.title}. {c.last}", c.last):
        add("CUSTOMER", c.full, _words(phrase))
    add("FIRST_NAME", c.first, _words(c.first), case_sensitive=c.first in names.WORD_FIRST_NAMES)
    F = re.escape(c.first[0])
    L = re.escape(c.last[0])
    # Initials: dotted and uppercase only (final-review ruling, narrowing spec §4 step 2). Undotted pairs are
    # ordinary words for some customers (UK, OR, IF, ID, IT ...); lowercase dotted pairs are a.m., e.g., n.b.
    # The final dot is required (a sentence break "the U.K. I live" is not initials) and customers whose pair is a
    # dotted abbreviation (U.K., e.g., P.S.) get no initials form.
    if c.first[0] + c.last[0] not in names.DOTTED_ABBREVIATIONS:
        add("CUSTOMER", c.full, rf"(?<![A-Za-z]){F}\.\s*{L}\.(?![A-Za-z])", case_sensitive=True)
    digits = _alnum(c.phone)
    add("PHONE", c.phone, r"\(?" + _seq(digits))
    add("PHONE", c.phone, r"(?<![A-Za-z0-9+])(?:\+|00)?" + SEP + "44" + SEP + r"(?:\(0\)" + SEP + ")?"
        + SEP.join(digits[1:]) + r"(?![A-Za-z0-9])")
    add("ACCOUNT", c.account, _seq(_alnum(c.account)))
    add("ACCOUNT", c.account, _seq(c.account[3:]))
    add("IBAN", c.iban, _seq(c.iban))
    add("ADDRESS", c.street, _words(c.street))
    add("POSTCODE", c.postcode, _seq(_alnum(c.postcode)))
    for o in c.orders:
        add("ORDER", o.order_no, _seq(_alnum(o.order_no)))
        add("ORDER", o.order_no, _seq(o.order_no.split("-")[1]))
    amounts = [p for o in c.orders for p in (*(i.price for i in o.items), o.total)]
    for p in dict.fromkeys(amounts):
        add("AMOUNT", money(p), amount_regex(p))
    return out


def mask_known(text: str, c: Customer, vault: Vault) -> tuple[str, list[Hit]]:
    """Replace every listed form of the sender's record. Overlaps go to the longest match. Every field is
    tokenised in the vault even when the text does not mention it, so the record summary can use it."""
    cands = []
    for f in forms(c):
        tok = vault.token(f.entity, f.canonical)
        cands += [Hit(f.entity, m.start(), m.end(), m.group(0), tok) for m in f.pattern.finditer(text)]
    chosen: list[Hit] = []
    for h in sorted(cands, key=lambda h: (-(h.end - h.start), h.start)):
        if all(h.end <= o.start or h.start >= o.end for o in chosen):
            chosen.append(h)
    chosen.sort(key=lambda h: h.start)
    parts, pos = [], 0
    for h in chosen:
        parts += [text[pos:h.start], h.token]
        pos = h.end
    parts.append(text[pos:])
    return "".join(parts), chosen
