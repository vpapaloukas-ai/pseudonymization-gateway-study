"""The scorer's own search for the sender's record in a text (spec §3 gold, §6 leaks). Written apart from
known.py on purpose, with broader separators, so the gold does not share the gateway's blind spots. It also
finds the forms the gateway does NOT list (nickname, town) and marks them unlisted."""
import re
from collections import Counter
from dataclasses import dataclass

from pgw import names
from pgw.crm import Customer

GAP = r"[^A-Za-z0-9\n]{0,2}"


@dataclass(frozen=True)
class Occurrence:
    field: str
    form: str
    text: str
    start: int
    end: int
    listed: bool


def _chars(s: str) -> str:
    chars = re.sub(r"[^A-Za-z0-9]", "", s)
    return r"(?<![A-Za-z0-9])" + GAP.join(map(re.escape, chars)) + r"(?![A-Za-z0-9])"


def _solid(digits: str) -> str:
    """Digit-only forms match contiguous digits only: no separators between them."""
    return r"(?<![A-Za-z0-9])" + re.escape(digits) + r"(?![A-Za-z0-9])"


def _phrase(s: str) -> str:
    return r"(?<![\w])" + r"\W{1,3}".join(map(re.escape, s.split())) + r"(?![\w])"


def _patterns(c: Customer) -> list[tuple[str, str, str, bool, int]]:
    """(field, form, regex, listed, flags)."""
    ci, cs = re.IGNORECASE, 0
    word_first = c.first in names.WORD_FIRST_NAMES
    F, L = re.escape(c.first[0]), re.escape(c.last[0])
    pats = [
        ("email", "address", re.escape(c.email), True, ci),
        ("email", "local", r"(?<![\w.])" + re.escape(c.email.split("@")[0]) + r"(?![\w])", True, ci),
        ("name", "full", _phrase(c.full), True, ci),
        ("name", "title_last", _phrase(f"{c.title} {c.last}"), True, ci),
        ("name", "title_last", _phrase(f"{c.title}. {c.last}"), True, ci),
        ("name", "last", _phrase(c.last), True, ci),
        ("name", "first", _phrase(c.first), True, cs if word_first else ci),
        ("phone", "national", _chars(c.phone), True, ci),
        ("phone", "international", r"\+?" + _chars("44" + re.sub(r"\D", "", c.phone)[1:]), True, ci),
        ("account", "account", _chars(c.account), True, ci),
        ("account", "digits", _solid(c.account[3:]), True, ci),
        ("iban", "iban", _chars(c.iban), True, ci),
        ("street", "street", _phrase(c.street), True, ci),
        ("postcode", "postcode", _chars(c.postcode), True, ci),
        ("town", "town", _phrase(c.town), False, ci),
    ]
    if c.first[0] + c.last[0] not in names.DOTTED_ABBREVIATIONS:   # dotted, uppercase, final dot required
        pats.append(("name", "initials", rf"(?<![A-Za-z]){F}\.\s*{L}\.(?![A-Za-z])", True, cs))
    if c.first in names.NICKNAMES:
        pats.append(("name", "nickname", _phrase(names.NICKNAMES[c.first]), False, cs))
    for o in c.orders:
        pats.append(("order", "order", _chars(o.order_no), True, ci))
        pats.append(("order", "digits", _solid(o.order_no.split("-")[1]), True, ci))
    for p in dict.fromkeys(p for o in c.orders for p in (*(i.price for i in o.items), o.total)):
        pounds, pence = divmod(p, 100)
        whole = f"{pounds:,}".replace(",", ",?")
        tail = rf"\.{pence:02d}" if pence else r"(?:\.00)?"
        pats.append(("amount", "amount", rf"£\s?{whole}{tail}(?!\d|\.\d)|(?<![\d.,£]){whole}\.{pence:02d}(?!\d|\.\d)", True, ci))
    return pats


def occurrences(text: str, c: Customer) -> list[Occurrence]:
    cands = [Occurrence(f, form, m.group(0), m.start(), m.end(), listed)
             for f, form, rx, listed, flags in _patterns(c) for m in re.finditer(rx, text, flags)]
    chosen: list[Occurrence] = []
    for o in sorted(cands, key=lambda o: (-(o.end - o.start), o.start)):
        if all(o.end <= x.start or o.start >= x.end for x in chosen):
            chosen.append(o)
    return sorted(chosen, key=lambda o: o.start)


def counts(text: str, c: Customer) -> Counter:
    return Counter((o.field, o.form, re.sub(r"[^a-z0-9£]", "", o.text.lower())) for o in occurrences(text, c))
