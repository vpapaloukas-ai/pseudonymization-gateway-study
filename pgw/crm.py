"""Seeded synthetic CRM of a fictional home-goods retailer (spec §3). No record describes a real person."""
import random
from dataclasses import dataclass
from datetime import date, timedelta

from pgw import names

REFERENCE_DATE = date(2026, 10, 5)   # "today" for the inbox; the system prompt states it (spec §5)
CRM_SEED = 1                          # one company, one CRM; dev and test draw different senders (spec §3)
DEV_PIDS = range(0, 100)
TEST_PIDS = range(100, 200)
WORD_NAME_PIDS = (60, 61, 62, 63, 160, 161, 162, 163)
INWARD = "ABDEFGHJLNPQRSTUWXYZ"


@dataclass(frozen=True)
class Item:
    name: str
    price: int   # pence


@dataclass(frozen=True)
class Order:
    order_no: str
    placed: date
    status: str              # processing | dispatched | delivered
    dispatched: date | None
    delivered: date | None
    items: tuple[Item, ...]

    @property
    def total(self) -> int:
        return sum(i.price for i in self.items)


@dataclass(frozen=True)
class Customer:
    pid: str
    title: str
    first: str
    last: str
    email: str
    phone: str
    street: str
    town: str
    postcode: str
    account: str
    iban: str
    orders: tuple[Order, ...]

    @property
    def full(self) -> str:
        return f"{self.first} {self.last}"


def money(pence: int) -> str:
    return f"£{pence // 100:,}.{pence % 100:02d}"


def iban_gb(bank: str, sort_code: str, account: str) -> str:
    """A GB IBAN with valid ISO 13616 check digits."""
    bban = bank + sort_code + account
    digits = "".join(str(int(c, 36)) for c in bban + "GB00")
    return f"GB{98 - int(digits) % 97:02d}{bban}"


def postcode(rng: random.Random) -> str:
    return (f"{rng.choice('BDHLNPSTWY')}{rng.choice('ABDEHLNRST')}{rng.randrange(1, 30)} "
            f"{rng.randrange(1, 10)}{rng.choice(INWARD)}{rng.choice(INWARD)}")


def _order(rng: random.Random, used: set[str]) -> Order:
    while True:
        order_no = f"BW-{rng.randrange(10**6):06d}"
        if order_no not in used:
            used.add(order_no)
            break
    age = rng.randint(1, 2) if rng.random() < 0.15 else rng.randrange(3, 60)
    placed = REFERENCE_DATE - timedelta(days=age)
    items = tuple(Item(n, p) for n, p in rng.sample(names.PRODUCTS, rng.randint(1, 3)))
    if age <= 2:
        return Order(order_no, placed, "processing", None, None, items)
    dispatched = placed + timedelta(days=rng.randint(1, 2))
    delivered = dispatched + timedelta(days=rng.randint(2, 6))
    late = rng.random() < 0.25 and (REFERENCE_DATE - dispatched).days <= 20
    if delivered > REFERENCE_DATE or late:
        return Order(order_no, placed, "dispatched", dispatched, None, items)
    return Order(order_no, placed, "delivered", dispatched, delivered, items)


def build_crm(seed: int = CRM_SEED, n: int = 200) -> list[Customer]:
    rng = random.Random(seed)
    phones = rng.sample(range(1000), n)
    word = dict(zip(WORD_NAME_PIDS, names.WORD_FIRST_NAMES))
    used_names: set[tuple[str, str]] = set()
    used_orders: set[str] = set()
    out = []
    for i in range(n):
        while True:
            first = word.get(i) or rng.choice(names.FIRST_NAMES)
            last = rng.choice(names.LAST_NAMES)
            if (first, last) not in used_names:
                used_names.add((first, last))
                break
        out.append(Customer(
            pid=f"C{i:03d}", title=rng.choice(names.TITLES), first=first, last=last,
            email=f"{first.lower()}.{last.lower()}@{rng.choice(names.MAIL_DOMAINS)}",
            phone=f"07700 900{phones[i]:03d}",
            street=f"{rng.randrange(1, 120)} {rng.choice(names.STREETS)}", town=rng.choice(names.TOWNS),
            postcode=postcode(rng), account=f"BWC{rng.randrange(10**7):07d}",
            iban=iban_gb("SYNT", f"{rng.randrange(10**6):06d}", f"{rng.randrange(10**8):08d}"),
            orders=tuple(_order(rng, used_orders) for _ in range(rng.randint(1, 3))),
        ))
    return out


def unused_phones(crm: list[Customer]) -> list[str]:
    taken = {c.phone for c in crm}
    return [p for p in (f"07700 900{k:03d}" for k in range(1000)) if p not in taken]
