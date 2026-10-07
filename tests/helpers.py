from datetime import date

from pgw.crm import Customer, Item, Order, iban_gb


def make_customer(first: str = "Ada", last: str = "Okafor", **overrides) -> Customer:
    """A fixed customer for logic tests: one delivered order (2 items) and one processing order."""
    fields = dict(
        pid="C900", title="Ms", first=first, last=last,
        email=f"{first.lower()}.{last.lower()}@postbox-mail.co.uk", phone="07700 900123",
        street="12 Larkspur Road", town="Whitby", postcode="YO21 3XX", account="BWC1234567",
        iban=iban_gb("SYNT", "123456", "12345678"),
        orders=(
            Order("BW-482913", date(2026, 9, 1), "delivered", date(2026, 9, 2), date(2026, 9, 5),
                  (Item("Ceramic table lamp", 4500), Item("Wool throw", 6500))),
            Order("BW-500001", date(2026, 10, 4), "processing", None, None, (Item("Jute rug", 12000),)),
        ),
    )
    fields.update(overrides)
    return Customer(**fields)


import re

from pgw.masking import Detection, Masked
from pgw.vault import TOKEN_RE


class FakeDetector:
    """Masks exactly the strings it is given, as PERSON, never inside an existing token: logic tests without spaCy."""

    entities = ["PERSON"]

    def __init__(self, strings: list[str]) -> None:
        self.strings = sorted(strings, key=len, reverse=True)

    def mask(self, text, vault):
        taken = [(m.start(), m.end()) for m in TOKEN_RE.finditer(text)]
        dets, out = [], text
        for s in self.strings:
            for m in re.finditer(re.escape(s), text):
                if all(m.end() <= a or m.start() >= b for a, b in taken):
                    dets.append(Detection("PERSON", m.start(), m.end(), 1.0))
            out = out.replace(s, vault.token("PERSON", s))
        return Masked(out, tuple(sorted(dets, key=lambda d: (d.start, d.end))))
